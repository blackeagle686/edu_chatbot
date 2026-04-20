import os
from fastapi import FastAPI, Request, Form, File, UploadFile, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from engine import irym_manager
from auth import register, login, make_session_token, verify_session_token, update_user_profile, get_user_sessions, get_session_messages, create_chat_session, add_chat_message
import uvicorn
import shutil
import uuid

app = FastAPI(title="Wasla Educational Chatbot")

# Setup templates and static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# Lifecycle
@app.on_event("startup")
async def startup_event():
    print("[*] FastAPI Startup: Initializing IRYM SDK components...")

    os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "uploads", "docs"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "uploads", "cvs"), exist_ok=True)

    data_dir = os.path.join(BASE_DIR, "data")
    await irym_manager.initialize(data_dir=data_dir)

    from IRYM_sdk import get_providers
    providers = get_providers()
    print(f"[+] IRYM SDK Providers: LLM={providers.get('llm')}, VLM={providers.get('vlm')}")
    print("[+] FastAPI Startup: Complete. Server ready.")


@app.on_event("shutdown")
async def shutdown_event():
    await irym_manager.shutdown()


# Auth Helpers
def _get_user(session: str | None) -> dict | None:
    if not session:
        return None
    return verify_session_token(session)


# Auth Routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, session: str = Cookie(default=None)):
    if _get_user(session):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    result = login(username, password)
    if not result.get("ok"):
        return templates.TemplateResponse("login.html", {"request": request, "error": result["error"]})
    token = make_session_token(username)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("session", token, httponly=True, max_age=86400 * 7)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, session: str = Cookie(default=None)):
    if _get_user(session):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
):
    result = register(username, password, role)
    if not result.get("ok"):
        return templates.TemplateResponse("register.html", {"request": request, "error": result["error"]})
    token = make_session_token(username)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("session", token, httponly=True, max_age=86400 * 7)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, session: str = Cookie(default=None)):
    user = _get_user(session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.post("/profile", response_class=HTMLResponse)
async def profile_submit(
    request: Request,
    full_name: str = Form(...),
    bio: str = Form(...),
    email: str = Form(""),
    profile_image: UploadFile = File(None),
    cv: UploadFile = File(None),
    session: str = Cookie(default=None)
):
    user = _get_user(session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    
    cv_filename = None
    if cv and cv.filename:
        ext = os.path.splitext(cv.filename)[1]
        cv_filename = f"cv_{user['username']}_{uuid.uuid4().hex[:8]}{ext}"
        cv_path = os.path.join(BASE_DIR, "uploads", "cvs", cv_filename)
        with open(cv_path, "wb") as buffer:
            shutil.copyfileobj(cv.file, buffer)
            
    img_filename = None
    if profile_image and profile_image.filename:
        ext = os.path.splitext(profile_image.filename)[1]
        img_filename = f"img_{user['username']}_{uuid.uuid4().hex[:8]}{ext}"
        img_path = os.path.join(BASE_DIR, "static", img_filename)
        with open(img_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)
            
    update_user_profile(user["username"], full_name, bio, email, img_filename, cv_filename)
    
    # Ingest CV into RAG for background awareness
    if cv_filename:
        try:
            cv_path = os.path.join(BASE_DIR, "uploads", "cvs", cv_filename)
            await irym_manager.rag.ingest(cv_path)
        except Exception as e:
            print(f"[!] CV Ingestion Error: {e}")
    
    # Refresh user data for the template
    updated_user = _get_user(session)
    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "user": updated_user, 
        "success": "Profile updated successfully!"
    })


# Chat History API Routes
@app.get("/api/sessions")
async def api_get_sessions(session: str = Cookie(default=None)):
    user = _get_user(session)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    sessions = get_user_sessions(user["username"])
    return JSONResponse({"sessions": sessions})

@app.get("/api/sessions/{session_id}")
async def api_get_session_messages(session_id: str, session: str = Cookie(default=None)):
    user = _get_user(session)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    messages = get_session_messages(session_id)
    return JSONResponse({"messages": messages})


# Main App Routes
@app.get("/landing", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: str = Cookie(default=None)):
    user = _get_user(session)
    if not user:
        return RedirectResponse("/landing", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.post("/chat")
async def chat(
    request: Request,
    message: str = Form(...),
    session_id: str = Form(""),
    role: str = Form("user"),
    image: UploadFile = File(None),
    session: str = Cookie(default=None),
):
    user = _get_user(session)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    username = user["username"]
    role = role or user.get("role", "user")
    
    if not session_id:
        session_id = str(uuid.uuid4())
        create_chat_session(username, session_id, title=message[:30] + "...")
    else:
        create_chat_session(username, session_id, title="Continued Chat")
        
    add_chat_message(session_id, "user", message)

    try:
        image_path = None
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1]
            filename = f"{uuid.uuid4()}{ext}"
            image_path = os.path.join(BASE_DIR, "uploads", filename)
            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

        response, docs, thinking = await irym_manager.get_response(
            message, session_id=session_id, image_path=image_path, role=role, user_profile=user
        )
        
        add_chat_message(session_id, "bot", response)
        
        return JSONResponse({
            "response": response, 
            "generated_docs": docs, 
            "thinking": thinking,
            "session_id": session_id
        })
    except Exception as e:
        import traceback
        print(f"[!] Critical Route Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": f"Server Error: {str(e)}"}, status_code=500)


@app.post("/upload_doc")
async def upload_doc(file: UploadFile = File(...), session: str = Cookie(default=None)):
    if not _get_user(session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
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
        traceback.print_exc()
        return JSONResponse({"error": f"Upload Error: {str(e)}"}, status_code=500)


@app.get("/download/{filename}")
async def download_doc(filename: str, session: str = Cookie(default=None)):
    if not _get_user(session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    # Check docs folder
    doc_path = os.path.join(BASE_DIR, "uploads", "docs", filename)
    if not os.path.exists(doc_path):
        # Check cvs folder
        doc_path = os.path.join(BASE_DIR, "uploads", "cvs", filename)
        
    if not os.path.exists(doc_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    original_name = filename.split("_", 1)[-1] if "_" in filename else filename
    return FileResponse(path=doc_path, filename=original_name, media_type='application/octet-stream')


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
