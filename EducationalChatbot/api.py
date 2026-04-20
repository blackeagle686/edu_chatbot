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

class RecommendRequest(BaseModel):
    query: str

@rec_router.post("/")
async def api_get_recommendations(request: RecommendRequest):
    try:
        helpers = await dotnet_client.get_recommendations(request.query)
        return {
            "status": "success",
            "data": {
                "helpers": helpers
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    sessionId: str
    message: str
    userId: str  # The unique ID from .NET
    role: str = "user"
    imagePath: Optional[str] = None

@ai_router.post("/chat")
async def api_chat(request: ChatRequest):
    try:
        # 1. Fetch user data from .NET instead of relying on frontend input
        user_profile = await dotnet_client.get_user_profile(request.userId)
        
        if not user_profile:
            # Fallback if .NET is down or user not found
            user_profile = {"username": request.userId, "full_name": "User", "bio": ""}

        # 2. Call the AI with the fetched profile
        response_text, docs, thinking, actions = await irym_manager.get_api_response(
            query=request.message,
            session_id=request.sessionId,
            image_path=request.imagePath,
            role=request.role,
            user_profile=user_profile
        )
        
        # 3. Process Recommendations automatically if triggered by AI
        final_helpers = []
        for action in actions:
            if action.get("type") == "RECOMMEND_HELPERS":
                query = action["payload"].get("query")
                try:
                    dotnet_helpers = await dotnet_client.get_recommendations(query)
                    final_helpers.extend(dotnet_helpers)
                except:
                    pass

        return {
            "status": "success",
            "data": {
                "responseText": response_text,
                "thinkingProcess": thinking,
                "generatedDocs": docs,
                "actions": actions,
                "recommendedHelpers": final_helpers
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@ai_router.post("/ingest")
async def api_ingest(file: UploadFile = File(...)):
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        doc_path = os.path.join(BASE_DIR, "uploads", "docs", filename)
        
        with open(doc_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        await irym_manager.rag.ingest(doc_path)
        
        return {
            "status": "success",
            "data": {
                "message": "Document ingested successfully."
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
