import os
import logging
from groq import Groq
from .ollama_client import BaseWebsiteGenerator

logger = logging.getLogger(__name__)

class GroqWebsiteGenerator(BaseWebsiteGenerator):
    """
    Client wrapper for Groq AI.
    Used for high-speed generation with Llama 3 70B/8B or Mixtral.
    """

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.environ.get("LLAMA_API_KEY")
        self.model = model
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def generate_website(self, brief: str, template_id: str = None) -> str:
        if not self.client:
            raise Exception("Groq API key (LLAMA_API_KEY) not found in environment.")

        logger.info(f"Groq Web Gen | Model: {self.model} | Brief: {brief[:50]}...")
        
        system_prompt = self._build_system_prompt()
        user_prompt = f"Build a complete, responsive webpage based on this brief: {brief}"
        if template_id:
            user_prompt += f"\nFollow the design language and structure of template: {template_id}"

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=8192,
            )
            raw_text = chat_completion.choices[0].message.content
            files = self.parse_multi_file_output(raw_text)
            
            if files and "index.html" in files:
                return self.merge_files_to_html(files)
            
            import re
            return re.sub(r'```(?:html|jsx|javascript|js)?\n?|```', '', raw_text, flags=re.IGNORECASE).strip()

        except Exception as e:
            logger.error(f"Groq Web Gen Error: {str(e)}")
            raise

    def stream_response(self, brief: str):
        if not self.client:
            logger.error("Groq API key missing for stream.")
            yield "<!-- Error: Groq API key missing -->"
            return

        system_prompt = self._build_system_prompt()
        user_prompt = f"Build a complete webpage based on this brief: {brief}"

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
            yield f"\n\n<!-- Error streaming Groq response: {str(e)} -->"
