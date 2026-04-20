from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from engine import irym_manager
from dotnet_client import dotnet_client
import os
import uuid
import shutil

ai_router = APIRouter(prefix="/api/v1/ai", tags=["AI Integration"])
rec_router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])

class UserContext(BaseModel):
    name: Optional[str] = "User"
    role: Optional[str] = "Seeker"
    skills: Optional[List[str]] = []
    location: Optional[str] = None
    completedTasks: Optional[int] = 0
    memberSince: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None

class SystemContext(BaseModel):
    availableCategories: Optional[List[str]] = []
    topHelpers: Optional[List[Dict[str, Any]]] = []
    recentTasks: Optional[List[Dict[str, Any]]] = []

class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    userId: str
    message: str
    userContext: Optional[UserContext] = None
    systemContext: Optional[SystemContext] = None
    conversationHistory: Optional[List[ConversationMessage]] = []
    metadata: Optional[Dict[str, Any]] = {}

@ai_router.post("/chat")
async def api_chat(request: ChatRequest):
    try:
        # Pass the full context to the engine
        # The engine will now return the raw structure for .NET
        result = await irym_manager.get_api_response(
            query=request.message,
            userId=request.userId,
            user_context=request.userContext.dict() if request.userContext else {},
            system_context=request.systemContext.dict() if request.systemContext else {},
            history=[m.dict() for m in request.conversationHistory] if request.conversationHistory else [],
            metadata=request.metadata
        )
        
        # Directly return the object expected by .NET (no wrapper)
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class IngestRequest(BaseModel):
    userId: str
    featureType: str
    fileContent: Optional[str] = None
    options: Optional[Dict[str, Any]] = {}

@ai_router.post("/ingest")
async def api_ingest(
    userId: str,
    featureType: str,
    file: UploadFile = File(...),
    options: Optional[str] = None  # JSON string from multipart
):
    try:
        import json
        parsed_options = json.loads(options) if options else {}
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        doc_path = os.path.join(BASE_DIR, "uploads", "docs", filename)
        
        with open(doc_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingest for RAG
        await irym_manager.rag.ingest(doc_path)
        
        # Extract text for analysis
        from wasla_tools import extract_file_content
        text_content = extract_file_content(doc_path)
        
        # Call engine for specific feature processing
        result = await irym_manager.process_ingest(
            userId=userId,
            featureType=featureType,
            text=text_content,
            filename=file.filename,
            options=parsed_options
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
