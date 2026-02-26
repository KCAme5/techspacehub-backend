import requests
import json
import logging
import os
import zipfile
import io
import re

logger = logging.getLogger(__name__)

class OllamaWebsiteGenerator:
    """
    Client wrapper for local Ollama AI.
    Runs locally alongside Django in Coolify/Docker.
    Optimized for 16GB RAM / CPU-only inference.
    """
    def __init__(self, model="llama3.1:8b", host="http://ollama-techspacehub:11434"):
        # local-ollama is the docker network hostname defined in docker-compose
        # fallback to localhost if testing locally outside docker
        self.host = os.environ.get("OLLAMA_HOST", host)
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.api_url = f"{self.host}/api/generate"
        
        # Aggressive memory constraints for 16GB RAM CPU-only
        self.options = {
            "num_ctx": 8192,      # Limit context window to save memory
            "num_thread": 2,      # Limit to 2 CPUs to prevent system lockup
            "temperature": 0.2,   # Lower temp for more deterministic code generation
            "top_p": 0.9,
        }

    def _build_system_prompt(self):
        return (
            "You are an expert AI web developer. "
            "Write highly modular, clean, and modern HTML, CSS (Tailwind), and JS. "
            "Return ONLY valid code. No markdown formatting, no explanations. "
            "Wrap everything in a single valid HTML file with embedded CSS/JS if applicable."
        )

    def generate_website(self, brief: str, template_id: str = None) -> str:
        """
        Full website generation (Blocking). 
        Returns the raw HTML string containing embedded CSS/JS.
        """
        logger.info(f"Ollama Web Gen | Model: {self.model} | Brief: {brief[:50]}...")
        
        prompt = f"System: {self._build_system_prompt()}\n\nUser: Build a complete, responsive webpage based on this brief: {brief}"
        if template_id:
            prompt += f"\nFollow the design language and structure of template: {template_id}"
            
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": self.options
        }
        
        try:
            # 5-minute timeout because CPU generation of 8K tokens takes time
            response = requests.post(self.api_url, json=payload, timeout=300)
            response.raise_for_status()
            
            # Clean up the response (remove Markdown blocks if the AI hallucinates them)
            raw_text = response.json().get('response', '')
            clean_html = re.sub(r"```html\n|```", "", raw_text).strip()
            
            return clean_html
            
        except requests.exceptions.ReadTimeout:
            logger.error("Ollama generation timed out after 5 minutes.")
            raise Exception("AI took too long to generate the website. Try a simpler prompt.")
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Ollama at {self.host}. Is the container running?")
            raise Exception("AI backend is currently unreachable.")
        except Exception as e:
            logger.error(f"Ollama Web Gen Error: {str(e)}")
            raise

    def generate_preview_code(self, brief: str) -> str:
        """
        Extremely fast, summarized generation for instant live UI previews.
        Uses lower token counts.
        """
        fast_options = self.options.copy()
        fast_options["num_predict"] = 2048 # Cap output length for speed
        
        prompt = f"System: {self._build_system_prompt()}\nUser: Build a VERY simple, fast layout mockup using Tailwind for this brief: {brief}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": fast_options
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            raw_text = response.json().get('response', '')
            return re.sub(r"```html\n|```", "", raw_text).strip()
        except Exception as e:
            logger.error(f"Preview Generation Error: {str(e)}")
            return "<html><body><h2>Preview Generation Failed</h2></body></html>"

    def stream_response(self, brief: str):
        """
        Generator for Server-Sent Events (SSE). Streams chunks back to UI.
        """
        prompt = f"System: {self._build_system_prompt()}\n\nUser: Build a complete webpage based on this brief: {brief}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self.options
        }
        
        try:
            with requests.post(self.api_url, json=payload, stream=True, timeout=60) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield chunk.get("response", "")
        except Exception as e:
            logger.error(f"Ollama Streaming Error: {str(e)}")
            yield f"\n\n<!-- Error streaming AI response: {str(e)} -->"

    @staticmethod
    def create_zip_archive(html_content: str, filename: str = "website.zip") -> io.BytesIO:
        """
        Utility function to package the generated HTML into a downloadable zip file.
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_content)
        zip_buffer.seek(0)
        return zip_buffer
