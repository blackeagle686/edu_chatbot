import os
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from engine import irym_manager
import uvicorn
import shutil
import uuid

app = FastAPI(title="IRYM Educational Chatbot")

# Setup templates and static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.on_event("startup")
async def startup_event():
    print("[*] FastAPI Startup: Initializing IRYM SDK components...")
    
    # Ensure uploads directory exists
    os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "uploads", "docs"), exist_ok=True)
    
    # Initialize IRYM SDK
    data_dir = os.path.join(BASE_DIR, "data")
    await irym_manager.initialize(data_dir=data_dir)
    
    # Log configured providers
    from IRYM_sdk import get_providers
    providers = get_providers()
    print(f"[+] IRYM SDK Providers: LLM={providers.get('llm')}, VLM={providers.get('vlm')}")
    
    print("[+] FastAPI Startup: Complete. Server ready.")

@app.on_event("shutdown")
async def shutdown_event():
    await irym_manager.shutdown()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(
    message: str = Form(...), 
    session_id: str = Form("default_user"),
    role: str = Form("user"),
    image: UploadFile = File(None)
):
    try:
        image_path = None
        if image and image.filename:
            # Create a unique filename to avoid collisions
            ext = os.path.splitext(image.filename)[1]
            filename = f"{uuid.uuid4()}{ext}"
            image_path = os.path.join(BASE_DIR, "uploads", filename)
            
            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
        
        response = await irym_manager.get_response(message, session_id=session_id, image_path=image_path, role=role)
        return JSONResponse({"response": response})
    except Exception as e:
        import traceback
        print(f"[!] Critical Route Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": f"Server Error: {str(e)}"}, status_code=500)

@app.post("/upload_doc")
async def upload_doc(file: UploadFile = File(...)):
    try:
        # Create a unique filename for the document
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        doc_path = os.path.join(BASE_DIR, "uploads", "docs", filename)
        
        with open(doc_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"[*] Uploaded document for RAG ingestion: {doc_path}")
        await irym_manager.rag.ingest(doc_path)
        return JSONResponse({"status": "success", "message": "Document ingested successfully"})
    except Exception as e:
        import traceback
        print(f"[!] Document Upload Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": f"Upload Error: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
