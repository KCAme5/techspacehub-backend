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

    def __init__(self, model="qwen2.5-coder:14b", host=None):
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.api_url = f"{self.host}/api/generate"

        # Optimized for 16GB RAM, 2 OCPUs
        self.options = {
            "num_ctx": 4096,  # Reduced context for conversation + code
            "num_thread": 2,  # Use both OCPUs
            "temperature": 0.3,  # Slightly higher for creative revisions
            "top_p": 0.9,
        }

    def _build_system_prompt(self, mode="generate", project_type="auto"):
        """Build system prompt based on mode and project type."""

        # Base prompt for all modes
        base_prompt = (
            "You are an expert AI web developer. "
            "Write highly modular, clean, and modern code. "
            "Return ONLY valid code. No markdown formatting, no explanations. "
        )

        if mode == "generate":
            if project_type == "react":
                return (
                    base_prompt + "Generate a React project with JSX files. "
                    "Use functional components with hooks. "
                    "Use Tailwind CSS from https://cdn.tailwindcss.com. "
                    "Return a JSON object with filenames as keys and file contents as values. "
                    'Example: {"index.html": "...", "App.jsx": "...", "styles.css": "..."}'
                )
            elif project_type == "multi_file":
                return (
                    base_prompt + "Generate separate HTML, CSS, and JS files. "
                    "Link them correctly: CSS in <head>, JS before </body>. "
                    "Use Tailwind CSS from https://cdn.tailwindcss.com. "
                    "Return a JSON object with filenames as keys and file contents as values. "
                    'Example: {"index.html": "...", "styles.css": "...", "script.js": "..."}'
                )
            else:  # single_file or auto
                return (
                    base_prompt + "Use Tailwind CSS from https://cdn.tailwindcss.com. "
                    "Wrap everything in a single valid HTML file with embedded CSS/JS if applicable."
                )

        elif mode == "revise":
            return (
                "You are an expert AI web developer helping revise a website. "
                "You will receive the current code and a user's request for changes. "
                "CRITICAL INSTRUCTION: Return the COMPLETE, FULL revised code with ALL changes applied. "
                "Do NOT return only the new parts or additions. "
                "Return the ENTIRE file content as it should appear after the changes. "
                "Return ONLY valid code. No markdown formatting, no explanations outside code blocks. "
                "Use Tailwind CSS from https://cdn.tailwindcss.com. "
                "If the project has multiple files, return a JSON object with all files."
            )

    def generate_initial(
        self, brief: str, project_type: str = "auto"
    ) -> Generator[str, None, None]:
        """Generate initial website from brief."""
        prompt = f"System: {self._build_system_prompt('generate', project_type)}\n\nUser: Build a complete webpage based on this brief: {brief}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self.options,
        }

        yield from self._stream_response(payload)

    def revise_website(
        self,
        current_code: str,
        user_request: str,
        conversation_history: List[Dict] = None,
    ) -> Generator[str, None, None]:
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
            "options": self.options,
        }

        yield from self._stream_response(payload)

    def _stream_response(self, payload: dict) -> Generator[str, None, None]:
        """Stream response from Ollama."""
        try:
            logger.info(f"Sending request to {self.api_url} with model {self.model}")
            with requests.post(
                self.api_url, json=payload, stream=True, timeout=300
            ) as r:
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
        clean = re.sub(r"```html\n|```|```html|```json\n|```json", "", raw_text).strip()
        return clean

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> dict:
        """
        Parse AI output that contains multiple files.
        Returns a dict mapping filenames to their contents.

        If the output is valid JSON with file mappings, use that.
        Otherwise, try to extract files from markdown code blocks.

        Returns: {filename: content, ...}
        """
        import re
        import json

        # First, try to parse as JSON
        try:
            # Clean markdown wrappers first
            cleaned = re.sub(
                r"^```json\s*|```$", "", raw_text.strip(), flags=re.MULTILINE
            )
            data = json.loads(cleaned)
            if isinstance(data, dict):
                # Filter out non-string values and non-file keys
                files = {
                    k: v for k, v in data.items() if isinstance(v, str) and "." in k
                }
                if files:
                    return files
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: Extract from markdown code blocks with filenames
        files = {}
        # Pattern: ```filename.ext\ncontent\n```
        pattern = r"```([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, raw_text, re.DOTALL)

        for filename, content in matches:
            filename = filename.strip()
            if "." in filename and not filename.startswith("//"):
                files[filename] = content.strip()

        # If no files found, treat entire output as single index.html
        if not files and raw_text.strip():
            return {"index.html": raw_text.strip()}

        return files

    @staticmethod
    def merge_files_to_html(files: dict) -> str:
        """
        Merge multiple files (HTML, CSS, JS) into a single HTML file for preview.
        This is used when the AI generates separate files but we need to preview as one.
        """
        html_content = files.get("index.html", "")

        # If no HTML file, create one
        if not html_content:
            html_content = "<!DOCTYPE html><html><head></head><body></body></html>"

        # Inject CSS files into <head>
        css_content = ""
        for filename, content in files.items():
            if filename.endswith(".css"):
                css_content += f"\n/* {filename} */\n{content}\n"

        if css_content and "<style>" not in html_content:
            css_tag = f"<style>{css_content}</style>"
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{css_tag}</head>")
            else:
                html_content = html_content.replace("</body>", f"{css_tag}</body>")

        # Inject JS files before </body>
        js_content = ""
        for filename, content in files.items():
            if filename.endswith(".js") and not filename.endswith(".jsx"):
                js_content += f"\n/* {filename} */\n{content}\n"

        if js_content:
            js_tag = f"<script>{js_content}</script>"
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{js_tag}</body>")
            else:
                html_content += js_tag

        return html_content
