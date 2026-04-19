import os
import asyncio
import random

class DotNetClient:
    def __init__(self):
        self.base_url = os.getenv("DOTNET_API_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("DOTNET_API_KEY", "")
        self.is_mock = not self.base_url  # Use mock if no URL is provided

    async def get_recommendations(self, query: str):
        """
        Fetches helper recommendations from the .NET backend.
        If no URL is configured, returns mock data for development.
        """
        if self.is_mock:
            return await self._get_mock_helpers(query)
        
        # Real implementation (Placeholder until URL/Schema is confirmed)
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = await client.get(
                    f"{self.base_url}/api/helpers/recommend", 
                    params={"query": query},
                    headers=headers,
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json()
                return []
        except Exception as e:
            print(f"[!] DotNet API Error: {e}")
            return []

    async def _get_mock_helpers(self, query: str):
        """Simulates a .NET API response with relevant experts."""
        await asyncio.sleep(0.5)  # Simulate network latency
        
        # Simple mock matching logic
        all_helpers = [
            {"name": "Ahmed Ali", "skills": ["Python", "Machine Learning", "FastAPI"], "url": "/profile/ahmed"},
            {"name": "Sara Hassan", "skills": ["React", "UI/UX", "JavaScript"], "url": "/profile/sara"},
            {"name": "John Doe", "skills": ["SQL", "Database", "Backend"], "url": "/profile/john"},
            {"name": "Laila Kamel", "skills": ["English", "Translation", "Content Writing"], "url": "/profile/laila"}
        ]
        
        # Filter based on query keywords
        query_lower = query.lower()
        matched = [
            h for h in all_helpers 
            if any(skill.lower() in query_lower for skill in h["skills"])
        ]
        
        # If no match, return a random selection
        return matched if matched else random.sample(all_helpers, 2)

dotnet_client = DotNetClient()
