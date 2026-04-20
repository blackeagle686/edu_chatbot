import re

with open("engine.py", "r") as f:
    content = f.read()

get_resp_code = re.search(r'(    async def get_response\(.*?\n.*?)(    async def _process_helper_recommendations)', content, re.DOTALL).group(1)

api_resp_code = get_resp_code.replace("def get_response(", "def get_api_response(")

# Replace the Profile update processing in the copy
old_profile_logic = """        # Process Profile Updates
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
            
        return new_resp, docs, thinking"""

new_api_logic = """        actions = []
        
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
                
                actions.append({
                    "type": "UPDATE_PROFILE",
                    "payload": {
                        "fullName": new_full_name,
                        "email": new_email,
                        "bio": new_bio
                    }
                })
                
                new_resp = re.sub(r'<UPDATE_PROFILE.*?>.*?(?:</UPDATE_PROFILE>)?', '', new_resp, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # Process Helper Recommendations
        if "<RECOMMEND_HELPERS>" in new_resp:
            import re
            match = re.search(r'<RECOMMEND_HELPERS>(.*?)</RECOMMEND_HELPERS>', new_resp, re.DOTALL)
            if match:
                helper_query = match.group(1).strip()
                actions.append({
                    "type": "RECOMMEND_HELPERS",
                    "payload": {
                        "query": helper_query
                    }
                })
                new_resp = new_resp.replace(match.group(0), "").strip()
        
        if hasattr(self, "memory_engine"):
            await self.memory_engine.add_interaction(session_id, query, new_resp)
            
        return new_resp, docs, thinking, actions"""

api_resp_code = api_resp_code.replace(old_profile_logic, new_api_logic)

content = content.replace("    async def _process_helper_recommendations", api_resp_code + "\n    async def _process_helper_recommendations")

with open("engine.py", "w") as f:
    f.write(content)
