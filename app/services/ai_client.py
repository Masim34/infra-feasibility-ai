"""
app/services/ai_client.py
Anthropic Claude API client for infrastructure narrative generation.
"""
import os
import httpx
from typing import Optional, Dict

class AnthropicClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    async def generate_narrative(self, prompt: str) -> str:
        if not self.api_key:
            return "Narrative generation unavailable: ANTHROPIC_API_KEY not configured."
            
        payload = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 4000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=self.headers, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"]
            except Exception as e:
                return f"Error generating narrative: {str(e)}"

ai_client = AnthropicClient()
