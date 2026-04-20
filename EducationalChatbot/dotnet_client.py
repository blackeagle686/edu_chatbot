import os
import asyncio
import random

class DotNetClient:
    def __init__(self):
        self.base_url = os.getenv("DOTNET_API_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("DOTNET_API_KEY", "")
        self.is_mock = not self.base_url  # Use mock if no URL is provided

    async def update_user_profile(self, user_id: str, data: dict):
        """
        Background sync to update user profile in .NET if triggered by AI.
        """
        if self.is_mock:
            print(f"[*] [MOCK] Updating profile for {user_id}: {data}")
            return True
            
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = await client.post(
                    f"{self.base_url}/api/user/profile/update-ai", 
                    json={"userId": user_id, "updates": data},
                    headers=headers,
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            print(f"[!] DotNet API Error: {e}")
            return False

dotnet_client = DotNetClient()
