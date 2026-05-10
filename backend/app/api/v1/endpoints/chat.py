from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest
from app.services.rag_engine import rag_engine

router = APIRouter()

@router.post("/query")
async def query_rag(request: ChatRequest):
    try:
        answer = await rag_engine.query(request.message)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
