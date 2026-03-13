import os
import logging
import json
import requests
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)

class GeminiBuilderClient(BaseWebsiteGenerator):
    """
    Client wrapper for Google Gemini AI for the builder app.
    Uses REST API to avoid library dependency issues.
    """

    def __init__(self, model="gemini-1.5-flash-latest"):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = model
        # Using v1 stable endpoint
        self.url = f"https://generativelanguage.googleapis.com/v1/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

    def stream_generation(self, prompt: str):
        if not self.api_key:
            logger.error("Gemini API key missing for stream.")
            return

        system_prompt = self._build_system_prompt()
        user_prompt = f"Build a complete, responsive React app based on this prompt: {prompt}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"System: {system_prompt}\n\nUser: {user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192,
            }
        }

        try:
            response = requests.post(self.url, json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8').strip()
                    if decoded.startswith('data: '):
                        try:
                            chunk_data = json.loads(decoded[6:])
                            if "candidates" in chunk_data:
                                content = chunk_data["candidates"][0].get("content", {})
                                parts = content.get("parts", [])
                                if parts:
                                    yield parts[0].get("text", "")
                        except json.JSONDecodeError:
                            continue
                    
        except Exception as e:
            logger.error(f"Gemini Streaming Error: {str(e)}")
            raise e
