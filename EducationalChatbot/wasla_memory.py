import time
import json

class WaslaMemoryEngine:
    """
    Hybrid semantic memory system.
    Combines exact caching, short-term conversational memory, and long-term
    semantic memory via LLM background extraction using event-driven logic.
    """
    def __init__(self, llm, vector_db):
        self.llm = llm
        self.vector_db = vector_db
        self.history = {}
        self.user_profiles = {}
        self.cache = {}
        # Short-term structured context memory per session
        self.context_memory = {}
        
    async def add_interaction(self, session_id: str, prompt: str, response: str):
        if session_id not in self.history:
            self.history[session_id] = []
            
        tags = self._lightweight_tag(prompt)
        
        self.history[session_id].append({
            "role": "user",
            "content": prompt,
            "tags": tags,
            "timestamp": time.time()
        })
        self.history[session_id].append({
            "role": "assistant",
            "content": response,
            "tags": [],
            "timestamp": time.time()
        })
        
        # Exact Semantic Cache
        if session_id not in self.cache:
            self.cache[session_id] = []
        self.cache[session_id].append({
            "query": prompt.lower().strip(),
            "response": response,
            "timestamp": time.time()
        })
        if len(self.cache[session_id]) > 20:
            self.cache[session_id].pop(0)

        # Event-driven extraction logic (Summarization Layer)
        # Avoid generating summaries on every message. Only trigger if history is large or "solved"
        prompt_lower = prompt.lower()
        is_solved = any(w in prompt_lower for w in ["solved", "thanks", "works", "fixed", "great", "yes"])
        
        # We use a naive length tracking. In production, we'd delete extracted history or mark it.
        # Here we just look at the last 6 messages if we haven't extracted recently.
        # For simplicity, if we hit 6+ msgs or is_solved, we trigger async extraction
        if len(self.history[session_id]) >= 6 or is_solved:
            await self._run_summarization_job(session_id)
            # clear history buffer that was extracted (except the last 2 to maintain conversational flow)
            self.history[session_id] = self.history[session_id][-2:]

    def _lightweight_tag(self, text: str) -> list:
        # Rule-based tagging to save LLM calls
        text_lower = text.lower()
        tags = []
        if "login" in text_lower or "auth" in text_lower or "password" in text_lower:
            tags.append("authentication")
        if "django" in text_lower:
            tags.append("django")
        if "error" in text_lower or "bug" in text_lower or "issue" in text_lower:
            tags.append("bug")
        if "payment" in text_lower or "card" in text_lower:
            tags.append("billing")
        return tags

    # Structured context memory helpers
    def add_context_entry(self, session_id: str, main_subject: str, summary_last_answer: str, usr_query: str):
        """Append a structured context entry for a session.

        Entry shape:
        {
            "main_subject": str,
            "summary_last_answer": str,
            "usr_query": str,
            "timestamp": float
        }
        """
        if session_id not in self.context_memory:
            self.context_memory[session_id] = []
        entry = {
            "main_subject": main_subject,
            "summary_last_answer": summary_last_answer,
            "usr_query": usr_query,
            "timestamp": time.time()
        }
        self.context_memory[session_id].append(entry)
        # keep a bounded history
        if len(self.context_memory[session_id]) > 50:
            self.context_memory[session_id].pop(0)
        return entry

    def get_current_context(self, session_id: str):
        """Return the most recent structured context entry for a session."""
        lst = self.context_memory.get(session_id, [])
        return lst[-1] if lst else None

    def change_main_subject(self, session_id: str, new_subject: str):
        """Change the `main_subject` for the current context entry.

        If no entry exists, a new one will be created with empty summary/query.
        """
        cur = self.get_current_context(session_id)
        if not cur:
            return self.add_context_entry(session_id, new_subject, "", "")
        cur["main_subject"] = new_subject
        cur["subject_changed_at"] = time.time()
        return cur

    async def _run_summarization_job(self, session_id: str):
        # Extract at most the last 8 messages
        recent_msgs = self.history[session_id][-8:]
        conv_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent_msgs])
        
        if not await self._should_extract(recent_msgs):
            return
            
        prompt = (
            "Analyze the following conversation and extract the core problem and solution. "
            "Respond ONLY with a valid JSON object matching this schema:\n"
            '{"problem": "short description of issue", "solution": "summary of the fix", "tags": ["tag1", "tag2"], "confidence": 0.9}\n\n'
            f"Conversation:\n{conv_text}"
        )
        try:
            if not self.llm:
                return
            summary_response = await self.llm.generate(prompt)
            import re
            json_match = re.search(r'\{.*\}', summary_response, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group(0))
                
                metadata = {
                    "type": "wasla_semantic_memory",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "tags": ",".join(extracted.get("tags", [])),
                    "confidence": extracted.get("confidence", 1.0)
                }
                text_to_embed = f"Problem: {extracted.get('problem')}\nSolution: {extracted.get('solution')}"
                if self.vector_db:
                    await self.vector_db.add(texts=[text_to_embed], metadatas=[metadata])
                    print(f"[*] Memory Engine extracted and stored knowledge: {text_to_embed[:30]}...")
        except Exception as e:
            print(f"[!] Background summarization failed: {e}")

    async def _should_extract(self, msgs) -> bool:
        # Avoid summarizing short chit-chat
        total_len = sum(len(m["content"]) for m in msgs)
        if total_len < 60:
            return False
        return True

    async def get_context(self, session_id: str, query: str) -> str:
        # 1. Check exact cache (Semantic Caching)
        cached_response = self._check_cache(session_id, query)
        if cached_response:
            return f"[CACHED_RESPONSE] {cached_response}"

        semantic_context = ""
        # 2. Retrieve Long-Term Memory
        if self.vector_db:
            try:
                results = await self.vector_db.search(query, limit=5)
                valid_results = []
                current_time = time.time()
                for res in results:
                    content = res.get("text", str(res)) if isinstance(res, dict) else str(res)
                    meta = res.get("metadata", {}) if isinstance(res, dict) else {}
                    
                    # Some memory DBs skip non-memory hits. We should only process 'wasla_semantic_memory'
                    # if it's mixed with RAG docs.
                    if meta.get("type", "") == "wasla_semantic_memory":
                        score = res.get("score", 1.0) if isinstance(res, dict) else 1.0
                        
                        age_seconds = current_time - meta.get("timestamp", current_time)
                        recency = max(0.0, 1.0 - (age_seconds / (30 * 24 * 3600)))
                        
                        # Hybrid scoring rule
                        hybrid_score = (0.7 * score) + (0.3 * recency)
                        if hybrid_score >= 0.70:
                            valid_results.append((hybrid_score, content))
                
                valid_results.sort(key=lambda x: x[0], reverse=True)
                if valid_results:
                    semantic_context = "\n[Long-Term Semantic Memory]\n" + "\n".join([f"- {r[1]}" for r in valid_results[:2]])
            except Exception as e:
                print(f"[!] Wasla Semantic Memory Search Failed: {e}")

        # 3. Form Short-Term Context
        short_term_context = ""
        if session_id in self.history:
            recent_msgs = self.history[session_id][-4:]
            short_term_context = "\n[Recent Conversation]\n" + "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent_msgs])

        # 4. Form Profile Context
        profile_context = ""
        if session_id in self.user_profiles:
            prof = self.user_profiles[session_id]
            profile_context = f"\n[User Profile: Level={prof.get('level', 'unknown')}, Interests={','.join(prof.get('interests', []))}]\n"

        return (semantic_context + short_term_context + profile_context).strip()
        
    def _check_cache(self, session_id: str, query: str) -> str:
        if session_id not in self.cache:
            return None
        q_lower = query.lower().strip()
        for c in reversed(self.cache[session_id]):
            if q_lower == c["query"]:
                return c["response"]
        return None
