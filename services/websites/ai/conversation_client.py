import requests
import json
import logging
import os
from typing import List, Dict, Generator
from django.conf import settings

logger = logging.getLogger(__name__)

class ConversationalAIClient:
    """
    Conversational AI client for website generation with context management.
    Maintains conversation history and code context for iterative improvements.
    """
    
    def __init__(self, model="llama3.1:8b", host=None):
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.api_url = f"{self.host}/api/generate"
        
        # Optimized for 16GB RAM, 2 OCPUs
        self.options = {
            "num_ctx": 4096,      # Reduced context for conversation + code
            "num_thread": 2,    # Use both OCPUs
            "temperature": 0.3,   # Slightly higher for creative revisions
            "top_p": 0.9,
        }
    
    def _build_system_prompt(self, mode='generate'):
        """Build system prompt based on mode."""
        if mode == 'generate':
            return (
                "You are an expert AI web developer. "
                "Write highly modular, clean, and modern HTML, CSS (Tailwind), and JS. "
                "Return ONLY valid code. No markdown formatting, no explanations. "
                "Wrap everything in a single valid HTML file with embedded CSS/JS if applicable."
            )
        elif mode == 'revise':
            return (
                "You are an expert AI web developer helping revise a website. "
                "You will receive the current code and a user's request for changes. "
                "Return the COMPLETE revised HTML file with all changes applied. "
                "Return ONLY valid code. No markdown formatting, no explanations. "
                "The code must be a complete, working HTML file."
            )
    
    def generate_initial(self, brief: str) -> Generator[str, None, None]:
        """Generate initial website from brief."""
        prompt = f"System: {self._build_system_prompt('generate')}\n\nUser: Build a complete webpage based on this brief: {brief}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self.options
        }
        
        yield from self._stream_response(payload)
    
    def revise_website(self, current_code: str, user_request: str, 
                      conversation_history: List[Dict] = None) -> Generator[str, None, None]:
        """
        Revise website based on user request and conversation history.
        
        Args:
            current_code: The current HTML/CSS/JS code
            user_request: What the user wants to change
            conversation_history: List of previous messages [{'role': 'user'/'assistant', 'content': '...'}]
        """
        # Build context from conversation history (last 5 exchanges to stay within token limits)
        context = ""
        if conversation_history:
            recent_history = conversation_history[-5:]  # Last 5 messages
            for msg in recent_history:
                context += f"\n{msg['role'].capitalize()}: {msg['content']}\n"
        
        # Build the revision prompt
        prompt = f"""System: {self._build_system_prompt('revise')}

Current website code:
```html
{current_code[:8000]}  # Limit code to prevent context overflow
```

Previous conversation:
{context}

User's new request: {user_request}

Based on the current code and the user's request, provide the COMPLETE revised HTML file with all changes applied:"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self.options
        }
        
        yield from self._stream_response(payload)
    
    def _stream_response(self, payload: dict) -> Generator[str, None, None]:
        """Stream response from Ollama."""
        try:
            logger.info(f"Sending request to {self.api_url} with model {self.model}")
            with requests.post(self.api_url, json=payload, stream=True, timeout=300) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            yield chunk.get("response", "")
                        except json.JSONDecodeError:
                            continue
        except requests.exceptions.Timeout:
            logger.error("Ollama timeout")
            yield "\n<!-- Error: AI generation timed out -->"
        except Exception as e:
            logger.error(f"Ollama error: {str(e)}")
            yield f"\n<!-- Error: {str(e)} -->"
    
    @staticmethod
    def clean_code_output(raw_text: str) -> str:
        """Clean up AI output - remove markdown code blocks."""
        import re
        # Remove markdown code blocks
        clean = re.sub(r"```html\n|```|```html", "", raw_text).strip()
        return clean
