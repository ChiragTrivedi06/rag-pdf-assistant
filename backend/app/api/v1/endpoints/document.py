from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import shutil
import os
import logging
from app.services.pdf_service import pdf_service
from app.services.rag_engine import rag_engine

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def process_and_index_pdf(file_path: str, filename: str):
    """
    Background task to process PDF and add to vector store.
    """
    try:
        logger.info(f"Starting background processing for {filename}")
        # Process PDF
        chunks = await pdf_service.process_pdf(file_path)
        logger.info(f"PDF {filename} split into {len(chunks)} chunks")
        
        # Add to Vector Store
        await rag_engine.add_documents(chunks)
        logger.info(f"Successfully indexed {filename}")
    except Exception as e:
        logger.error(f"Error processing {filename}: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@router.post("/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        content = await file.read()
        if len(content) == 0:
            raise Exception("File is empty")
            
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # Add processing to background tasks
        background_tasks.add_task(process_and_index_pdf, file_path, file.filename)
        
        return {
            "message": f"Upload successful. {file.filename} is being processed in the background.",
            "filename": file.filename
        }
    
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))
