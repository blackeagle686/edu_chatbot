from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from engine import irym_manager
import os
import uuid

# Remove prefix so it matches POST {AIService:BaseUrl}/chat and /ingest exactly
ai_router = APIRouter(prefix="/api/v1/ai", tags=["AI Integration"])

class UserContext(BaseModel):
    name: Optional[str] = "User"
    role: Optional[str] = "Seeker"
    skills: Optional[List[str]] = []
    location: Optional[str] = None
    completedTasks: Optional[int] = 0
    memberSince: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    currentHeadline: Optional[str] = None
    currentBio: Optional[str] = None
    experience: Optional[str] = None

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
        # The engine will return the raw structure for .NET
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


class FileMetadata(BaseModel):
    fileName: str
    contentType: Optional[str] = None
    size: Optional[int] = 0
    pageCount: Optional[int] = 0

class IngestRequest(BaseModel):
    userId: str
    featureType: str
    fileContent: Optional[str] = None
    fileMetadata: Optional[FileMetadata] = None
    userContext: Optional[UserContext] = None
    options: Optional[Dict[str, Any]] = {}
    metadata: Optional[Dict[str, Any]] = {}

@ai_router.post("/ingest")
async def api_ingest(request: IngestRequest):
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        filename = request.fileMetadata.fileName if request.fileMetadata else f"{uuid.uuid4()}.txt"
        
        # Ingest requires a file path, so we save the extracted text sent by .NET to a local temp file
        doc_path = os.path.join(BASE_DIR, "uploads", "docs", filename)
        
        if request.fileContent:
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(request.fileContent)
                
            # Ingest for RAG
            await irym_manager.rag.ingest(doc_path)
            
            text_content = request.fileContent
        else:
            text_content = ""
            
        # Call engine for specific feature processing
        result = await irym_manager.process_ingest(
            userId=request.userId,
            featureType=request.featureType,
            text=text_content,
            filename=filename,
            options=request.options
        )
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
