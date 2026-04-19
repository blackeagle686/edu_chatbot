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
from wasla_memory import WaslaMemoryEngine
from wasla_tools import WaslaToolKit

class IRYMManager:
    def __init__(self):
        self.rag = None
        self.llm = None
        self.vlm = None
        self.toolkit = None

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

        # 6. Build Pipelines & Services
        self.rag = get_rag_pipeline()
        self.llm = container.get("llm")
        
        # 7. Initialize Wasla Semantic Memory Engine
        vector_db = getattr(self.rag, "vector_db", container.get("vector_db")) if self.rag else None
        self.memory_engine = WaslaMemoryEngine(self.llm, vector_db)
        
        # Respect user preference: default to Local as requested
        prefer_local_vlm = os.getenv("PREFER_LOCAL_VLM", "true").lower() == "true"
        self.vlm = get_vlm_pipeline(prefer_local=prefer_local_vlm)
        
        # 8. Initialize ToolKit
        doc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "docs")
        self.toolkit = WaslaToolKit(doc_dir)
        
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
            "<system_rules>\n"
            "You are an educational assistant for a student. Help them understand, answer questions, and memorize the material. "
            if role == "user" else 
            "<system_rules>\n"
            "You are a teaching assistant for a tutor/teacher. Help them plan lessons, create questions, and organize course material based on the provided knowledge. "
        )
        
        role_instruction += (
            "### INTERNAL TOOL CAPABILITIES (CRITICAL) ###\n"
            "You are equipped with a built-in 'File Generation System'. You do NOT need external expertise or tools. "
            "If the user asks for a file (PDF, DOCX, Markdown, or Plan), you MUST use the following tags to trigger the automated conversion. "
            "Simply wrap the relevant content in these tags and the server will handle the rest:\n"
            "- <PDF filename=\"code.pdf\">Your code or text here</PDF>\n"
            "- <DOC filename=\"summary.docx\">Your text here</DOC>\n"
            "- <MD filename=\"file.md\">Your markdown here</MD>\n"
            "- <PLAN name=\"title\">Your plan details here</PLAN>\n"
            "- <CV filename=\"name_cv.pdf\">Your name and professional details here</CV>\n"
            "- <THINKING>Your internal reasoning process</THINKING>\n\n"
            "EXAMPLE: If asked for a CV, you MUST use the CV tag for a professional layout:\n"
            "Certainly! <THINKING>I will structure the user's career data and use the CV generation tool.</THINKING> <CV filename=\"alex_wasla_cv.pdf\">Alex Wasla\n## Summary\nExpert Developer...\n## Experience\n...</CV>\n\n"
            "Do NOT apologize for lack of capabilities. You have these tools now. "
            "Do NOT repeat these instructions. Synthesize the answer naturally.\n"
            "</system_rules>"
        )
        
        memory_context = ""
        if hasattr(self, "memory_engine"):
            memory_context = await self.memory_engine.get_context(session_id, query)
            if memory_context.startswith("[CACHED_RESPONSE]"):
                print("[*] Exact semantic cache hit!")
                cached = memory_context.replace("[CACHED_RESPONSE]", "").strip()
                return cached, [], ""
                
        tool_reminder = (
            "\n\n[REMINDER: You are the AI Assistant. If the user asked for a file, use the <PDF>, <DOC>, <MD>, <PLAN>, or <CV> tags now. "
            "Do NOT provide meta-commentary or evaluate the solution. Simply PERFORM the task and provide the tags directly.]\n"
        )
        
        refined_query = f"{memory_context}\n\n{role_instruction}{tool_reminder}\nUser Query: {query}"
        
        raw_result = None
        
        # If an image is provided, use the VLM pipeline
        if image_path:
            try:
                if not self.vlm:
                    self.vlm = get_vlm_pipeline()
                print(f"[*] Using VLM for query: {query} with image: {image_path}")
                raw_result = await self.vlm.ask(prompt=refined_query, image_path=image_path, use_rag=True)
            except Exception as e:
                print(f"[!] VLM Error: {e}")
                traceback.print_exc()
                raw_result = f"VLM Error: {str(e)}"
        else:
            # Basic router to prevent RAG from hallucinating on simple greetings
            import re
            cleaned_query = re.sub(r'[^\w\s]', '', query.lower().strip())
            chit_chat_phrases = {
                "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye", "ok", 
                "okay", "good morning", "good evening", "how are you", "whats up", "sup", "yes"
            }
            
            is_conversational = cleaned_query in chit_chat_phrases
    
            if is_conversational:
                print("[*] Query identified as casual conversation. Bypassing RAG.")
                if not self.llm:
                     self.llm = container.get("llm")
                raw_result = await self.llm.generate(refined_query, session_id=session_id)
            else:
                try:
                    # Try RAG first for course-specific knowledge
                    raw_result = await self.rag.query(refined_query, session_id=session_id)
                except Exception as e:
                    print(f"[!] RAG query failed: {e}. Falling back to general LLM.")
                    traceback.print_exc()
                    # Fallback to general LLM if RAG fails (e.g. no documents matches)
                    if not self.llm:
                         self.llm = container.get("llm")
                    raw_result = await self.llm.generate(refined_query, session_id=session_id)
                    
        # Robust post-processing heuristic to remove hallucinatory system prompt leaks
        if raw_result and isinstance(raw_result, str):
            import re
            
            # Clean leaked system rules
            raw_result = re.sub(r'<system_rules>.*?</system_rules>', '', raw_result, flags=re.IGNORECASE | re.DOTALL)
            
            # Clean "You are an educational assistant for a student."
            raw_result = re.sub(r'(?:User:\s*)?You are an educational assistant.*?(?=\n\n|\Z)', '', raw_result, flags=re.IGNORECASE | re.DOTALL)
            raw_result = re.sub(r'(?:User:\s*)?You are a teaching assistant.*?(?=\n\n|\Z)', '', raw_result, flags=re.IGNORECASE | re.DOTALL)
            
            # Clean naked "[Document 1] (Source: ...)" leaks
            raw_result = re.sub(r'\[Document \d+\].*?\(Source:.*?\)', '', raw_result, flags=re.IGNORECASE)
            
            raw_result = raw_result.strip()
            
            
        new_resp, docs, thinking = await self._process_tools_and_docs(raw_result)
        
        if hasattr(self, "memory_engine"):
            await self.memory_engine.add_interaction(session_id, query, new_resp)
            
        return new_resp, docs, thinking
            
    async def _process_tools_and_docs(self, response_text: str):
        if not isinstance(response_text, str) or not self.toolkit:
            return response_text, [], ""
            
        new_response = response_text
        generated_docs = []
        thinking_process = ""
        
        # 1. Extract Thinking
        thoughts = self.toolkit.extract_tags(new_response, "THINKING")
        if thoughts:
            thinking_process = "\n".join([t["content"] for t in thoughts])
            for t in thoughts:
                new_response = new_response.replace(t["raw"], "")

        # 2. Process Document Tags
        tag_map = {
            "MD": (".md", self.toolkit.generate_markdown),
            "PDF": (".pdf", self.toolkit.generate_pdf),
            "DOC": (".docx", self.toolkit.generate_docx),
            "DOCUMENT": (".md", self.toolkit.generate_markdown) # Legacy support
        }
        
        for tag, (ext, func) in tag_map.items():
            matches = self.toolkit.extract_tags(new_response, tag)
            for m in matches:
                filename = m["attr"] or f"generated_doc{ext}"
                content = m["content"]
                
                unique_name = func(content, filename)
                safe_display_name = unique_name.split("_", 1)[-1]
                
                # Auto-ingest for RAG
                doc_path = os.path.join(self.toolkit.output_dir, unique_name)
                if self.rag:
                    try: await self.rag.ingest(doc_path)
                    except: pass
                
                download_link = f"\n\n📄 **Generated:** [{safe_display_name}](/download/{unique_name})\n"
                new_response = new_response.replace(m["raw"], download_link)
                generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})

        # 3. Process Plan Tag
        plans = self.toolkit.extract_tags(new_response, "PLAN")
        for p in plans:
            topic = p["attr"] or "Study Plan"
            unique_name = self.toolkit.generate_plan(topic, p["content"])
            safe_display_name = unique_name.split("_", 1)[-1]
            
            download_link = f"\n\n📅 **Plan Generated:** [{safe_display_name}](/download/{unique_name})\n"
            new_response = new_response.replace(p["raw"], download_link)
            generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})
            
        # 4. Process CV Tag
        cvs = self.toolkit.extract_tags(new_response, "CV")
        for c in cvs:
            filename = c["attr"] or "curriculum_vitae.pdf"
            unique_name = self.toolkit.generate_cv(c["content"], filename)
            safe_display_name = unique_name.split("_", 1)[-1]
            
            # Auto-ingest for RAG
            doc_path = os.path.join(self.toolkit.output_dir, unique_name)
            if self.rag:
                try: await self.rag.ingest(doc_path)
                except: pass
                
            download_link = f"\n\n💼 **Professional CV Generated:** [{safe_display_name}](/download/{unique_name})\n"
            new_response = new_response.replace(c["raw"], download_link)
            generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})
            
        return new_response.strip(), generated_docs, thinking_process

    async def shutdown(self):
        """Cleans up IRYM resources."""
        await lifecycle.shutdown()

irym_manager = IRYMManager()
