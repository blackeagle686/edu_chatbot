import os
import sys
import asyncio

# Ensure IRYM_sdk is in the path if running from subfolder
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from IRYM_sdk import init_irym_full, get_rag_pipeline, get_vlm_pipeline
    from IRYM_sdk.core.container import container
except ImportError:
    # Fallback to absolute imports if needed
    from IRYM_sdk.IRYM import init_irym_full, get_rag_pipeline, get_vlm_pipeline
    from IRYM_sdk.core.container import container

from IRYM_sdk.core.lifecycle import lifecycle

class IRYMManager:
    def __init__(self):
        self.rag = None
        self.llm = None
        self.vlm = None

    async def initialize(self, data_dir: str = "data"):
        """Initializes the IRYM SDK and ingests data for RAG."""
        # Ensure we are in a proper async environment
        await init_irym_full()
        self.rag = get_rag_pipeline()
        self.vlm = get_vlm_pipeline()
        
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
