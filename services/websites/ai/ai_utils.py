import logging
import os
from .groq_client import GroqWebsiteGenerator
from .ollama_client import OllamaWebsiteGenerator, BaseWebsiteGenerator

logger = logging.getLogger(__name__)

class UniversalGenerator:
    """
    Unified AI utility that tries Groq first and falls back to Ollama.
    """
    
    def __init__(self):
        self.groq = GroqWebsiteGenerator()
        self.ollama = OllamaWebsiteGenerator()
        self.use_groq = bool(os.environ.get("LLAMA_API_KEY"))

    def generate_website(self, brief: str, template_id: str = None) -> str:
        if self.use_groq:
            try:
                logger.info("Attempting high-speed Groq generation...")
                return self.groq.generate_website(brief, template_id)
            except Exception as e:
                logger.warning(f"Groq failed or out of credit: {str(e)}. Falling back to Ollama.")
        
        return self.ollama.generate_website(brief, template_id)

    def stream_response(self, brief: str):
        if self.use_groq:
            try:
                logger.info("Streaming via Groq...")
                # We need to verify if the stream actually works or if it's out of credit early
                # For now, we yield from Groq, and if it fails immediately, we can't easily fallback mid-stream 
                # without complicated state management. But we'll try catching initial connection.
                for chunk in self.groq.stream_response(brief):
                    if "Error: Groq API key missing" in chunk or "Error streaming Groq response" in chunk:
                         raise Exception("Groq stream error")
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Groq streaming failed: {str(e)}. Falling back to Ollama.")

        yield from self.ollama.stream_response(brief)

class GroqConversationalClient(BaseWebsiteGenerator):
    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.environ.get("LLAMA_API_KEY")
        self.model = model
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def stream_revision(self, user_message, current_code, history):
        if not self.client: raise Exception("Groq key missing")
        
        system_prompt = (
            "You are an expert Frontend Developer. Revise the website based on the user's request. "
            "Return the COMPLETE content of every updated file. Use the marker format: --- filename ---\n"
            "Current code context is provided below."
        )
        
        # Format history and current code for context
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-5:]: # Last 5 messages for context
            messages.append({"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]})
        
        messages.append({"role": "user", "content": f"Current Code:\n{current_code}\n\nUser Request: {user_message}"})

        try:
            stream = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.2,
                max_tokens=8192,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq Revision Stream Error: {str(e)}")
            raise

class UniversalConversationalClient:
    def __init__(self):
        from .conversation_client import ConversationalAIClient
        self.groq = GroqConversationalClient()
        self.ollama = ConversationalAIClient()
        self.use_groq = bool(os.environ.get("LLAMA_API_KEY"))

    def stream_revision(self, user_message, current_code, history):
        if self.use_groq:
            try:
                # Test connection/credit by checking if client exists and trying a small yield
                for chunk in self.groq.stream_revision(user_message, current_code, history):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Groq revision failed, falling back to Ollama: {str(e)}")
        
        yield from self.ollama.stream_revision(user_message, current_code, history)

def get_universal_generator():
    return UniversalGenerator()

def get_universal_conversational_client():
    return UniversalConversationalClient()
