import os
import sys
import asyncio

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
        # 1. Disable blocking interactive prompts for headless environment
        config.AUTO_ACCEPT_FALLBACK = True
        
        # 2. Initialize Service Registry
        init_irym()
        
        # 3. Configure Providers (allows switching between OpenAI and Local via ENV)
        llm_provider = os.getenv("LLM_PROVIDER", "auto")
        vlm_provider = os.getenv("VLM_PROVIDER", "auto")
        set_providers(llm_provider=llm_provider, vlm_provider=vlm_provider)
        
        # 4. Start Connections and Lifecycle
        await startup_irym()
        await lifecycle.startup()

        # 5. Build Pipelines
        self.rag = get_rag_pipeline()
        
        # Respect VLM preference: default to Local if available, else OpenAI
        prefer_local_vlm = os.getenv("PREFER_LOCAL_VLM", "true").lower() == "true"
        self.vlm = get_vlm_pipeline(prefer_local=prefer_local_vlm)
        
        # Ingest educational data if the directory exists
        if os.path.exists(data_dir) and os.listdir(data_dir):
            print(f"[*] Ingesting educational data from {data_dir}...")
            await self.rag.ingest(data_dir)
        else:
            print("[!] No educational data found to ingest.")

    async def get_response(self, query: str, session_id: str = "default_user", image_path: str = None):
        """Queries the RAG pipeline or VLM for a response."""
        if not self.rag:
            raise RuntimeError("IRYM Manager not initialized. Call initialize() first.")
        
        # If an image is provided, use the VLM pipeline
        if image_path:
            if not self.vlm:
                self.vlm = get_vlm_pipeline()
            print(f"[*] Using VLM for query: {query} with image: {image_path}")
            return await self.vlm.ask(prompt=query, image_path=image_path, use_rag=True)

        try:
            # Try RAG first for course-specific knowledge
            response = await self.rag.query(query)
            return response
        except Exception as e:
            print(f"[!] RAG query failed: {e}. Falling back to general LLM.")
            # Fallback to general LLM if RAG fails (e.g. no documents matches)
            if not self.llm:
                 self.llm = container.get("llm")
            return await self.llm.generate(query, session_id=session_id)

    async def shutdown(self):
        """Cleans up IRYM resources."""
        await lifecycle.shutdown()

irym_manager = IRYMManager()
