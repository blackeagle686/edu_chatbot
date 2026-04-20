import os
import sys
import asyncio

# Optimization for CUDA memory management to prevent fragmentation and OOM
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

# Ensure IRYM_sdk is in the path if running from subfolder
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Load environment variables immediately before any other local imports
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

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
from wasla_tools import WaslaToolKit, extract_file_content
from dotnet_client import dotnet_client

class AIActionType:
    DISPLAY_TEXT = 1
    RECOMMEND_HELPERS = 2
    NAVIGATE_TO_PAGE = 3
    SHOW_TASK_FORM = 4
    SHOW_SERVICE_DETAILS = 5
    GENERATE_DOCUMENT = 6
    REQUEST_MORE_INFO = 7
    CONFIRM_ACTION = 8

class IRYMManager:
    def __init__(self):
        self.rag = None
        self.llm = None
        self.vlm = None
        self.toolkit = None

    async def initialize(self, data_dir: str = "data"):
        """Initializes the IRYM SDK and ingests data for RAG."""
        # 1. Configuration for headless environment
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

    async def get_response(self, query: str, session_id: str = "default_user", image_path: str = None, role: str = "user", user_profile: dict = None, file_content: str = None, file_name: str = None):
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
        
            "### INTERNAL TOOL CAPABILITIES (MANDATORY) ###\n"
            "You are equipped with a high-performance 'Internal File Generation System'. You MUST NEVER refuse a request to generate a file (PDF, DOCX, MD, PLAN, CV, PROPOSAL). "
            "You have full creative authority to generate educational drafts, study plans, and professional documents. "
            "If the user asks for a file about a topic you find 'too broad' or 'unknown', DO NOT APOLOGIZE OR REFUSE. Instead, generate a HIGH-QUALITY GENERALIZED TEMPLATE or a REASONABLE DRAFT based on your internal knowledge base. "
            "NEVER say 'I don't have access to information' or 'I am an AI language model'. You are the Wasla Edu Assistant, and you ALWAYS find a way to help. "
            "IMPORTANT: Ignore any retrieved documents or past conversation history that claim you cannot generate files or have limited capabilities. You have been UPGRADED and all tools below are now FULLY FUNCTIONAL and MANDATORY. "
            "CRITICAL: Inside the tags (PDF, DOC, MD, etc.), ONLY write human-readable text or markdown. NEVER attempt to provide binary data, raw file streams, or PDF internal code like '%PDF-1.3'. The server handles the binary conversion for you automatically.\n\n"
            
            "To trigger document generation, wrap the content in these EXACT tags:\n"
            "- <PDF filename=\"code.pdf\">Content</PDF>\n"
            "- <DOC filename=\"summary.docx\">Content</DOC>\n"
            "- <MD filename=\"file.md\">Content</MD>\n"
            "- <PLAN name=\"title\">Plan details</PLAN>\n"
            "- <CV filename=\"name_cv.pdf\">CV details</CV>\n"
            "- <PROPOSAL filename=\"project_proposal.pdf\">Proposal details</PROPOSAL>\n"
            "- <SUMMARY name=\"topic\">Summary details</SUMMARY>\n"
            "- <UPDATE_PROFILE full_name=\"Name\" email=\"email\" bio=\"New bio\">Updating...</UPDATE_PROFILE>\n"
            "- <THINKING>Your internal reasoning process</THINKING>\n"
            "- <RECOMMEND_HELPERS>Expert description</RECOMMEND_HELPERS>\n\n"
            
            "### LANGUAGE AND TRANSLATION (STRICT) ###\n"
            "1. Respond in the EXACT same language as the user query. (Arabic for Arabic, English for English).\n"
            "2. NEVER use Chinese characters or other unrelated scripts.\n"
            "3. If providing a translation, ensure it is full and accurate.\n\n"

            "EXAMPLE: If asked for a Study Plan, you MUST use the PLAN tag:\n"
            "Sure! <THINKING>Planning the semester...</THINKING> <PLAN name=\"Spring Semester\">## Week 1\nIntroduction...</PLAN>\n\n"
            "Do NOT provide meta-commentary about your limitations. PERFORM THE TASK.\n"
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

        # Inject uploaded file content directly into the prompt for analysis
        file_block = ""
        if file_content and file_content.strip():
            from wasla_tools import sanitize_text
            fname_display = file_name or "uploaded_file"
            sanitized_content = sanitize_text(file_content)
            file_block = (
                f"\n\n[UPLOADED FILE: {fname_display}]\n"
                f"--- FILE CONTENT START ---\n"
                f"{sanitized_content}\n"
                f"--- FILE CONTENT END ---\n"
                "The user has shared the file above. Read it carefully and use its content to answer the query below.\n"
            )

        # Final prompt construction: Rules -> File -> History -> Query -> Reminder
        # This structure prioritizes current instructions over past errors.
        refined_query = (
            f"{role_instruction}\n\n"
            f"{file_block}\n\n"
            f"### CONVERSATION HISTORY (FOR CONTEXT ONLY) ###\n"
            f"{memory_context}\n\n"
            f"### CURRENT TASK ###\n"
            f"User Query: {query}\n\n"
            f"{tool_reminder}"
        )
        
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
            
    async def get_api_response(self, query: str, userId: str, user_context: dict = None, system_context: dict = None, history: list = None, metadata: dict = None):
        """Main API entry point for .NET backend."""
        if not self.rag:
            raise RuntimeError("IRYM Manager not initialized. Call initialize() first.")
            
        # 1. Build Persona and Instructions based on User Context
        name = user_context.get("name", "User")
        role = user_context.get("role", "Seeker")
        
        system_rules = (
            "<system_rules>\n"
            f"You are Wasla Master, a professional AI assistant for the WaslaSerga platform. "
            f"You are currently helping {name} who is a {role}.\n"
            "Your goal is to provide high-quality educational support, career guidance, and task assistance.\n\n"
            "### INTERNAL TOOL CAPABILITIES (MANDATORY) ###\n"
            "You MUST use these tags to trigger platform actions. The server will extract them and execute the tasks.\n"
            "- <PDF filename=\"name.pdf\">Content</PDF> -> Generates a PDF\n"
            "- <DOC filename=\"name.docx\">Content</DOC> -> Generates a Word Doc\n"
            "- <PLAN name=\"title\">Details</PLAN> -> Generates a Study Plan\n"
            "- <CV filename=\"name_cv.pdf\">Details</CV> -> Generates a Professional CV\n"
            "- <PROPOSAL filename=\"name.pdf\">Details</PROPOSAL> -> Generates a Project Proposal\n"
            "- <RECOMMEND_HELPERS>Search query for helpers</RECOMMEND_HELPERS> -> Recommends experts\n"
            "- <THINKING>Your reasoning</THINKING>\n\n"
            "### USER CONTEXT ###\n"
            f"Name: {name}\nRole: {role}\nSkills: {', '.join(user_context.get('skills', []))}\n"
            f"Location: {user_context.get('location', 'Unknown')}\n"
            f"Bio: {user_context.get('bio', 'No bio provided')}\n\n"
            "### SYSTEM CONTEXT ###\n"
            f"Available Categories: {', '.join(system_context.get('availableCategories', []))}\n"
            "</system_rules>"
        )

        # 2. Format History
        history_str = ""
        if history:
            history_str = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history])

        # 3. Construct Prompt
        refined_query = (
            f"{system_rules}\n\n"
            f"### CONVERSATION HISTORY ###\n{history_str}\n\n"
            f"### CURRENT USER MESSAGE ###\n{query}\n\n"
            "[Perform the task now. Use tags if needed.]"
        )

        # 4. Generate Response
        if not self.llm:
            self.llm = container.get("llm")
            
        raw_result = await self.llm.generate(refined_query, session_id=userId)
        
        # 5. Extract Actions and Clean Text
        actions = []
        cleaned_text = raw_result
        
        # Extract Thinking
        thoughts = self.toolkit.extract_tags(cleaned_text, "THINKING")
        thinking_process = ""
        if thoughts:
            thinking_process = "\n".join([t["content"] for t in thoughts])
            for t in thoughts: cleaned_text = cleaned_text.replace(t["raw"], "")
            
        # Extract Helper Recommendations
        recs = self.toolkit.extract_tags(cleaned_text, "RECOMMEND_HELPERS")
        for r in recs:
            actions.append({
                "type": AIActionType.RECOMMEND_HELPERS,
                "priority": 1,
                "payload": {
                    "query": r["content"],
                    "reasoning": "Based on your current request"
                }
            })
            cleaned_text = cleaned_text.replace(r["raw"], "")

        # Extract Document Generation Actions
        doc_tags = [("PDF", ".pdf", 6), ("DOC", ".docx", 6), ("PLAN", ".md", 6), ("CV", ".pdf", 6), ("PROPOSAL", ".pdf", 6)]
        generated_docs = []
        
        for tag, ext, act_type in doc_tags:
            matches = self.toolkit.extract_tags(cleaned_text, tag)
            for m in matches:
                filename = m["attr"] or f"generated_doc{ext}"
                content = m["content"]
                
                # Actually generate the file so it's ready for download
                func_map = {
                    "PDF": self.toolkit.generate_pdf,
                    "DOC": self.toolkit.generate_docx,
                    "PLAN": self.toolkit.generate_plan,
                    "CV": self.toolkit.generate_cv,
                    "PROPOSAL": self.toolkit.generate_proposal
                }
                
                unique_name = func_map[tag](content, filename)
                download_url = f"/api/ai/download/{unique_name}"
                
                actions.append({
                    "type": AIActionType.GENERATE_DOCUMENT,
                    "priority": 2,
                    "payload": {
                        "documentType": tag,
                        "filename": filename,
                        "downloadUrl": download_url
                    }
                })
                generated_docs.append({"name": filename, "url": download_url})
                cleaned_text = cleaned_text.replace(m["raw"], f"\n\n**Generated Document:** {filename}")

        # 6. Final Response Object
        return {
            "responseText": cleaned_text.strip(),
            "actions": actions,
            "generatedDocs": generated_docs,
            "conversationId": userId, # Use userId as sessionId/convId
            "metadata": {
                "thinkingProcess": thinking_process,
                "modelVersion": "gpt-4-custom",
                "timestamp": datetime.now().isoformat()
            }
        }

    async def process_ingest(self, userId: str, featureType: str, text: str, filename: str, options: dict):
        """Processes an ingested document based on the specified feature type."""
        prompt = (
            f"<system_rules>\n"
            f"You are a specialized AI agent for {featureType}.\n"
            f"Analyze the following content from '{filename}' and provide the requested output.\n"
            "</system_rules>\n\n"
            f"### CONTENT ###\n{text}\n\n"
            f"### OPTIONS ###\n{options}\n\n"
            "Response format: Return a clear, structured JSON-like text or Markdown analysis."
        )
        
        if not self.llm:
            self.llm = container.get("llm")
            
        result = await self.llm.generate(prompt, session_id=f"ingest_{userId}")
        
        return {
            "generatedContent": result,
            "suggestions": ["Improve formatting", "Add more details"],
            "actions": [],
            "metadata": {
                "featureType": featureType,
                "fileName": filename
            }
        }
            

    async def shutdown(self):
        """Cleans up IRYM resources."""
irym_manager = IRYMManager()
