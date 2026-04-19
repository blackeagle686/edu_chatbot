import os
import subprocess
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

print("[*] Installing dependencies...")
install("fastapi")
install("uvicorn[standard]")
install("jinja2")
install("python-multipart")
install("pyngrok")
install("python-dotenv") # Required by IRYM_sdk

# Automatically install the local IRYM_sdk folder
parent_dir = os.path.dirname(os.path.abspath(__file__))
sdk_dir = os.path.join(os.path.dirname(parent_dir), "IRYM_sdk")

if os.path.exists(sdk_dir):
    print(f"[*] Found IRYM_sdk at {sdk_dir}. Installing local version...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", sdk_dir])
else:
    print("[!] IRYM_sdk folder not found in parent directory. Ensure it is uploaded correctly.")

from pyngrok import ngrok

# --- Configuration ---
PORT = 8000
NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN", "") # Optional: Set as env var

if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

print("[*] Starting ngrok tunnel...")
try:
    # Use explicit 127.0.0.1 to avoid IPv6 localhost issues
    public_url = ngrok.connect(addr=f"127.0.0.1:{PORT}", proto="http").public_url
    print(f"\n[!] Public URL: {public_url}")
    print("[!] Open this URL in your browser to access the IRYM Educational Chatbot.\n")
except Exception as e:
    print(f"[X] Failed to start ngrok: {e}")
    print("Hint: If you're on Colab, you might need an ngrok auth token for persistent connections.")

print("[*] Starting FastAPI server...")
# Run uvicorn in the background or use subprocess
# Since we want to see logs, we'll use subprocess and block
try:
    # Use 'main:app' assuming this script is in the same directory as main.py
    # or use the EducationalChatbot directory
    if os.path.exists("EducationalChatbot"):
        os.chdir("EducationalChatbot")
    
    subprocess.run(["uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(PORT)])
except KeyboardInterrupt:
    print("\n[*] Stopping server...")
    ngrok.kill()
