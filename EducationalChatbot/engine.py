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
from dotnet_client import dotnet_client

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

    async def get_response(self, query: str, session_id: str = "default_user", image_path: str = None, role: str = "user", user_profile: dict = None):
        """Queries the RAG pipeline or VLM for a response."""
        import traceback
        
        if not self.rag:
            raise RuntimeError("IRYM Manager not initialized. Call initialize() first.")
            
        role_instruction = (
            "<system_rules>\n"
            "You are an educational assistant for a student. Help them understand, answer questions, and memorize the material. "
            if role == "user" else 
            "<system_rules>\n"
            "You are a teaching assistant and career helper for a tutor/freelancer. Help them plan lessons, create questions, organize course material, and write proposals. "
        )
        
        if user_profile:
            full_name = user_profile.get("full_name") or "User"
            bio = user_profile.get("bio") or "No background information provided."
            email = user_profile.get("email") or "Not provided"
            role_type = user_profile.get("role", "user")
            has_cv = bool(user_profile.get("cv_filename"))
            has_image = bool(user_profile.get("profile_image"))
            
            role_instruction += f"\n[User Identity]\nName: {full_name}\nEmail: {email}\nBio/Background: {bio}\nRole: {role_type}\nHas Profile Image: {'Yes' if has_image else 'No'}\n"
            if has_cv:
                role_instruction += "Context: The user has provided a background CV. Prioritize this information for career or experience-related questions.\n"
            
            role_instruction += f"\nImportant: Always address the user as '{full_name}' to make the experience personalized.\n"
            
        if role == "user":
            role_instruction += (
                "When the user explains a problem, shares an idea, or uploads project documents, assess the complexity:\n"
                "- If Easy: Provide a direct solution.\n"
                "- If Medium: Provide a hint and use the <RECOMMEND_HELPERS> tag to recommend an expert.\n"
                "- If Hard: Do not provide a direct solution, use the <RECOMMEND_HELPERS> tag to recommend an expert.\n"
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
            "- <PROPOSAL filename=\"project_proposal.pdf\">Your proposal content here</PROPOSAL>\n"
            "- <UPDATE_PROFILE full_name=\"Name\" email=\"email\" bio=\"New bio\">Updating...</UPDATE_PROFILE>\n"
            "- <THINKING>Your internal reasoning process</THINKING>\n"
            "- <RECOMMEND_HELPERS>A short description of what kind of expert is needed</RECOMMEND_HELPERS>\n\n"
            
            "### LANGUAGE AND TRANSLATION (STRICT) ###\n"
            "1. You MUST respond in the EXACT SAME language the user uses. If the user asks in Arabic, respond in Arabic ONLY.\n"
            "2. NEVER switch to another language (like Chinese, Spanish, etc.) mid-response.\n"
            "3. If the user asks for a translation of English RAG data, provide the FULL translation in ARABIC. Do NOT mix languages.\n"
            "4. Ensure the Arabic terminology is correct (e.g., use 'الحوسبة السحابية' for 'Cloud Computing', not Chinese characters).\n"
            "5. If you cannot translate a specific technical term, keep it in English but DO NOT use Chinese or other scripts.\n\n"

            "EXAMPLE: If asked for a Proposal, you MUST use the PROPOSAL tag:\n"
            "Certainly! <THINKING>I will structure the proposal.</THINKING> <PROPOSAL filename=\"client_proposal.pdf\">## Introduction\nWe can help you...</PROPOSAL>\n\n"
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
            "\n\n[REMINDER: You are the AI Assistant. If the user asked for a file, use the <PDF>, <DOC>, <MD>, <PLAN>, <CV>, or <PROPOSAL> tags now. "
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
            
            
        # Process tools and docs
        new_resp, docs, thinking = await self._process_tools_and_docs(raw_result)
        
        # Process Profile Updates
        if "<UPDATE_PROFILE" in new_resp and user_profile:
            import re
            profile_update_match = re.search(r'<UPDATE_PROFILE\s+(.*?)\s*/?>.*?(?:</UPDATE_PROFILE>)?', new_resp, re.IGNORECASE | re.DOTALL)
            if profile_update_match:
                attrs_str = profile_update_match.group(1)
                name_m = re.search(r'full_name=["\'](.*?)["\']', attrs_str)
                email_m = re.search(r'email=["\'](.*?)["\']', attrs_str)
                bio_m = re.search(r'bio=["\'](.*?)["\']', attrs_str)
                
                new_full_name = name_m.group(1) if name_m else user_profile.get("full_name", "")
                new_email = email_m.group(1) if email_m else user_profile.get("email", "")
                new_bio = bio_m.group(1) if bio_m else user_profile.get("bio", "")
                
                from auth import update_user_profile
                update_user_profile(user_profile["username"], new_full_name, new_bio, email=new_email, profile_image=user_profile.get("profile_image"), cv_filename=user_profile.get("cv_filename"))
                
                new_resp = re.sub(r'<UPDATE_PROFILE.*?>.*?(?:</UPDATE_PROFILE>)?', '\n\n**Profile successfully updated.**\n', new_resp, flags=re.IGNORECASE | re.DOTALL)
        
        # 10. Process Helper Recommendations (if triggered by AI)
        new_resp = await self._process_helper_recommendations(new_resp)
        
        if hasattr(self, "memory_engine"):
            await self.memory_engine.add_interaction(session_id, query, new_resp)
            
        return new_resp, docs, thinking
            
    async def _process_helper_recommendations(self, response_text: str):
        if "<RECOMMEND_HELPERS>" not in response_text:
            return response_text
            
        import re
        match = re.search(r'<RECOMMEND_HELPERS>(.*?)</RECOMMEND_HELPERS>', response_text, re.DOTALL)
        if not match:
            return response_text
            
        query = match.group(1).strip()
        helpers = await dotnet_client.get_recommendations(query)
        
        if not helpers:
            return response_text.replace(match.group(0), "\n\n*Currently, no experts are available for this specific request. Please try again later.*")
            
        rec_block = "\n\n### Recommended Experts for You\n"
        for h in helpers:
            rec_block += f"- **{h['name']}** ({', '.join(h['skills'])}) — [View Profile]({h['url']})\n"
            
        return response_text.replace(match.group(0), rec_block)

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
                
                download_link = f"\n\n**Document Generated:** [{safe_display_name}](/download/{unique_name})\n"
                new_response = new_response.replace(m["raw"], download_link)
                generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})

        # 3. Process Plan Tag
        plans = self.toolkit.extract_tags(new_response, "PLAN")
        for p in plans:
            topic = p["attr"] or "Study Plan"
            unique_name = self.toolkit.generate_plan(topic, p["content"])
            safe_display_name = unique_name.split("_", 1)[-1]
            
            download_link = f"\n\n**Plan Generated:** [{safe_display_name}](/download/{unique_name})\n"
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
                
            download_link = f"\n\n**CV Generated:** [{safe_display_name}](/download/{unique_name})\n"
            new_response = new_response.replace(c["raw"], download_link)
            generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})
            
        # 5. Process Proposal Tag
        proposals = self.toolkit.extract_tags(new_response, "PROPOSAL")
        for p in proposals:
            filename = p["attr"] or "project_proposal.pdf"
            unique_name = self.toolkit.generate_proposal(p["content"], filename)
            safe_display_name = unique_name.split("_", 1)[-1]
            
            doc_path = os.path.join(self.toolkit.output_dir, unique_name)
            if self.rag:
                try: await self.rag.ingest(doc_path)
                except: pass
                
            download_link = f"\n\n**Proposal Generated:** [{safe_display_name}](/download/{unique_name})\n"
            new_response = new_response.replace(p["raw"], download_link)
            generated_docs.append({"name": safe_display_name, "url": f"/download/{unique_name}"})
            
        return new_response.strip(), generated_docs, thinking_process

    async def shutdown(self):
        """Cleans up IRYM resources."""
        await lifecycle.shutdown()

irym_manager = IRYMManager()
