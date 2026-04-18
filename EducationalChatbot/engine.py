import os
import sys
import asyncio

# Optimization for CUDA memory management to prevent fragmentation and OOM
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

# Ensure IRYM_sdk is in the path if running from subfolder
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from IRYM_sdk import (
        init_irym, 
        startup_irym, 
        get_rag_pipeline, 
        get_vlm_pipeline, 
        set_providers
    )
    from IRYM_sdk.core.container import container
    from IRYM_sdk.core.config import config
except ImportError:
    # Fallback to absolute imports if needed
    from IRYM_sdk.IRYM import (
        init_irym, 
        startup_irym, 
        get_rag_pipeline, 
        get_vlm_pipeline, 
        set_providers
    )
    from IRYM_sdk.core.container import container
    from IRYM_sdk.core.config import config

from IRYM_sdk.core.lifecycle import lifecycle

class IRYMManager:
    def __init__(self):
        self.rag = None
        self.llm = None
        self.vlm = None

    async def initialize(self, data_dir: str = "data"):
        """Initializes the IRYM SDK and ingests data for RAG."""
        # 1. Force load environment variables from local .env
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path)

        # 2. Disable blocking interactive prompts for headless environment (Crucial!)
        config.AUTO_ACCEPT_FALLBACK = True
        
        # 3. Initialize Service Registry
        init_irym()
        
        # 4. Configure Providers as requested by user
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        vlm_provider = os.getenv("VLM_PROVIDER", "local")
        
        print(f"[*] Configuring providers: LLM={llm_provider}, VLM={vlm_provider}")
        set_providers(llm_provider=llm_provider, vlm_provider=vlm_provider)
        
        # 5. Start Connections and Lifecycle
        await startup_irym()
        await lifecycle.startup()

        # 6. Build Pipelines
        self.rag = get_rag_pipeline()
        
        # Respect user preference: default to Local as requested
        prefer_local_vlm = os.getenv("PREFER_LOCAL_VLM", "true").lower() == "true"
        self.vlm = get_vlm_pipeline(prefer_local=prefer_local_vlm)
        
        # Ingest educational data if the directory exists
        if os.path.exists(data_dir) and os.listdir(data_dir):
            print(f"[*] Ingesting educational data from {data_dir}...")
            await self.rag.ingest(data_dir)
        else:
            print("[!] No educational data found to ingest.")

    async def get_response(self, query: str, session_id: str = "default_user", image_path: str = None, role: str = "user"):
        """Queries the RAG pipeline or VLM for a response."""
        import traceback
        
        if not self.rag:
            raise RuntimeError("IRYM Manager not initialized. Call initialize() first.")
            
        role_instruction = (
            "You are an educational assistant for a student. Help them understand, answer questions, and memorize the material. "
            if role == "user" else 
            "You are a teaching assistant for a tutor/teacher. Help them plan lessons, create questions, and organize course material based on the provided knowledge. "
        )
        
        refined_query = f"{role_instruction}\nUser Query: {query}"
        
        # If an image is provided, use the VLM pipeline
        if image_path:
            try:
                if not self.vlm:
                    self.vlm = get_vlm_pipeline()
                print(f"[*] Using VLM for query: {query} with image: {image_path}")
                return await self.vlm.ask(prompt=refined_query, image_path=image_path, use_rag=True)
            except Exception as e:
                print(f"[!] VLM Error: {e}")
                traceback.print_exc()
                return f"VLM Error: {str(e)}"

        try:
            # Try RAG first for course-specific knowledge
            response = await self.rag.query(refined_query, session_id=session_id)
            return response
        except Exception as e:
            print(f"[!] RAG query failed: {e}. Falling back to general LLM.")
            traceback.print_exc()
            # Fallback to general LLM if RAG fails (e.g. no documents matches)
            if not self.llm:
                 self.llm = container.get("llm")
            return await self.llm.generate(refined_query, session_id=session_id)

    async def shutdown(self):
        """Cleans up IRYM resources."""
        await lifecycle.shutdown()

irym_manager = IRYMManager()
