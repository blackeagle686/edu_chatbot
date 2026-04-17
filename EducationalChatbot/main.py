import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from engine import irym_manager
import uvicorn

app = FastAPI(title="IRYM Educational Chatbot")

# Setup templates and static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.on_event("startup")
async def startup_event():
    # Initialize IRYM SDK
    data_dir = os.path.join(BASE_DIR, "data")
    await irym_manager.initialize(data_dir=data_dir)

@app.on_event("shutdown")
async def shutdown_event():
    await irym_manager.shutdown()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(message: str = Form(...), session_id: str = Form("default_user")):
    try:
        response = await irym_manager.get_response(message, session_id=session_id)
        return JSONResponse({"response": response})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
