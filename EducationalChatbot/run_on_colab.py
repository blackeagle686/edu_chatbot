import os
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

print("[*] Installing dependencies...")
install("fastapi")
install("uvicorn")
install("jinja2")
install("python-multipart")
install("pyngrok")
# Assuming IRYM_sdk is available in the current directory or can be installed
# In Colab, the user would usually clone the repo first.
# If it's not installed, we might need:
# install("git+https://github.com/user/IRYM_sdk.git") 

from pyngrok import ngrok

# --- Configuration ---
PORT = 8000
NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN", "") # Optional: Set as env var

if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

print("[*] Starting ngrok tunnel...")
try:
    public_url = ngrok.connect(PORT).public_url
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
