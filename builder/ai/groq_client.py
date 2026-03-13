import os
import logging
from groq import Groq
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)

class GroqBuilderClient(BaseWebsiteGenerator):
    """
    Client wrapper for Groq AI for the builder app.
    """

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.environ.get("LLAMA_API_KEY")
        
        # Handle aliases or specific model requests
        if model == 'llama':
            self.model = "llama-3.3-70b-versatile"
        elif model == 'deepseek':
            self.model = "deepseek-r1-distill-qwen-32b"
        else:
            self.model = model
            
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def stream_generation(self, prompt: str):
        if not self.client:
            logger.error("Groq API key missing for stream.")
            yield "data: {\"error\": \"Groq API key missing\"}\n\n"
            return

        system_prompt = self._build_system_prompt()
        user_prompt = f"Build a complete, responsive React app based on this prompt: {prompt}"

        try:
            stream = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=8192,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq Streaming Error: {str(e)}")
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
