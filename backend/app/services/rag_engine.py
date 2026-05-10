import os
import logging
from typing import List, Optional, TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from langchain_core.documents import Document
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langgraph.graph import StateGraph, END
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class State(TypedDict):
    messages: List[AnyMessage]
    context: str
    source: str
    question: str

class RAGEngine:
    def __init__(self):
        # 1. Local Embeddings (MiniLM) - No more 504 errors!
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # 2. LLM (Gemini)
        self.llm = ChatGoogleGenerativeAI(
            model=settings.MODEL_NAME,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        
        # 3. Qdrant Client (Local Storage)
        self.client = QdrantClient(
            path=os.path.join(settings.VECTOR_STORE_PATH, "qdrant")
        )
        self.collection_name = "document_vectors"
        self._ensure_collection()
        
        # 4. Vector Store
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )
        
        # 5. LangGraph setup
        self.graph = self._build_graph()

    def _ensure_collection(self):
        """Ensure the Qdrant collection exists."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=384,  # all-MiniLM-L6-v2 dimension
                        distance=qmodels.Distance.COSINE
                    )
                )
        except Exception as e:
            print(f"Error ensuring Qdrant collection: {e}")

    def _build_graph(self):
        builder = StateGraph(State)
        
        # Define nodes
        builder.add_node("check_pdf", self._node_check_pdf)
        builder.add_node("answer_from_pdf", self._node_answer_from_pdf)
        builder.add_node("tavily_search", self._node_tavily_search)
        builder.add_node("answer_from_tavily", self._node_answer_from_tavily)
        
        # Define edges
        builder.set_entry_point("check_pdf")
        
        builder.add_conditional_edges(
            "check_pdf",
            lambda state: "answer_from_pdf" if state["source"] == "pdf" else "tavily_search",
            {
                "answer_from_pdf": "answer_from_pdf",
                "tavily_search": "tavily_search"
            }
        )
        
        builder.add_edge("tavily_search", "answer_from_tavily")
        builder.add_edge("answer_from_pdf", END)
        builder.add_edge("answer_from_tavily", END)
        
        return builder.compile()

    def _get_content(self, message):
        """Handle LLM response content (Gemini sometimes returns a list of parts)."""
        content = message.content
        if isinstance(content, list):
            return " ".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
        return str(content)

    # Nodes
    def _node_check_pdf(self, state: State):
        query = state["question"]
        logger.info(f"Checking PDF context for query: '{query}'")
        results = self.vector_store.similarity_search(query, k=5)
        
        if not results:
            logger.info("No relevant PDF context found. Routing to web search.")
            return {"source": "web", "context": ""}
        
        context = "\n\n".join([doc.page_content for doc in results])
        
        # Ask LLM if the context answers the question
        prompt = ChatPromptTemplate.from_template(
            "Question: {question}\n\nContext:\n{context}\n\n"
            "Does the context directly and sufficiently answer the question? Reply only 'YES' or 'NO'."
        )
        decision = self.llm.invoke(prompt.format(question=query, context=context))
        content = self._get_content(decision)
        
        if content.strip().upper().startswith("YES"):
            logger.info("Relevant PDF context found and validated. Routing to PDF answer generator.")
            return {"source": "pdf", "context": context}
        else:
            logger.info("PDF context found but deemed insufficient by LLM. Routing to web search.")
            return {"source": "web", "context": ""}

    def _node_answer_from_pdf(self, state: State):
        query = state["question"]
        context = state["context"]
        logger.info("Generating answer from PDF context.")
        
        prompt = ChatPromptTemplate.from_template(
            "Answer the question based ONLY on this context from the uploaded documents:\n{context}\n\nQuestion: {query}"
        )
        response = self.llm.invoke(prompt.format(query=query, context=context))
        
        return {
            "messages": state["messages"] + [AIMessage(content=self._get_content(response))],
            "source": "pdf"
        }

    def _node_tavily_search(self, state: State):
        if not settings.TAVILY_API_KEY:
            logger.warning("Tavily API key missing. Cannot perform web search.")
            return {"source": "error", "context": "Tavily API Key not configured."}
            
        query = state["question"]
        logger.info(f"Performing Tavily web search for: '{query}'")
        search_wrapper = TavilySearchAPIWrapper(tavily_api_key=settings.TAVILY_API_KEY)
        tavily = TavilySearchResults(api_wrapper=search_wrapper, max_results=5)
        try:
            results = tavily.invoke({"query": query})
            logger.info(f"Tavily search successful. Found {len(results)} snippets.")
            context = "\n\n".join([r["content"] for r in results])
            return {"source": "tavily", "context": context}
        except Exception as e:
            logger.error(f"Tavily search failed: {str(e)}")
            return {"source": "error", "context": f"Search failed: {str(e)}"}

    def _node_answer_from_tavily(self, state: State):
        query = state["question"]
        context = state["context"]
        
        if state["source"] == "error":
            logger.info("Web search failed. Returning error message.")
            return {"messages": state["messages"] + [AIMessage(content=f"Sorry, I couldn't find an answer in the documents and web search failed: {context}")]}

        logger.info("Generating answer from web search results.")
        prompt = ChatPromptTemplate.from_template(
            "Summarize and answer the question using ONLY this web search context:\n{context}\n\nQuestion: {query}"
        )
        response = self.llm.invoke(prompt.format(query=query, context=context))
        
        return {
            "messages": state["messages"] + [AIMessage(content=self._get_content(response))],
            "source": "tavily"
        }

    async def add_documents(self, documents: List[Document]):
        """Add documents to Qdrant."""
        try:
            # HuggingFaceEmbeddings is local, so this should be fast and reliable
            self.vector_store.add_documents(documents)
            print(f"Successfully added {len(documents)} documents to Qdrant.")
        except Exception as e:
            print(f"Error adding documents to Qdrant: {str(e)}")
            raise e

    async def query(self, question: str) -> str:
        """Query the RAG system using LangGraph."""
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "context": "",
            "source": "",
            "question": question
        }
        
        result = self.graph.invoke(initial_state)
        last_message = result["messages"][-1]
        return last_message.content

rag_engine = RAGEngine()
