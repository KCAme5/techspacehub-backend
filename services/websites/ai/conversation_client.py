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
        
        base_rules = (
            "You are an expert Frontend Web Developer. "
            "Build high-quality, professional websites using React and Tailwind CSS. "
            "CRITICAL RULES:\n"
            "1. OUTPUT FORMAT: Output multiple files using the marker format:\n"
            "   --- index.html ---\n"
            "   --- App.jsx ---\n"
            "   --- styles.css ---\n"
            "2. NO IMPORTS: Do NOT use `import ... from ...`. React/ReactDOM are global.\n"
            "3. STYLING: Use Tailwind CSS ONLY. Target a premium, modern aesthetic.\n"
            "4. INDEX.HTML: Clean structure, <div id='root'></div>, NO <script src='...'> for local files.\n"
            "5. APP.JSX: Main entry point. End with `ReactDOM.createRoot(document.getElementById('root')).render(<App />);`."
        )

        if mode == "generate":
            return f"{base_rules}\n\nReturn ONLY the files. No explanations."
        
        elif mode == "revise":
            return (
                f"{base_rules}\n\n"
                "You are helping revise a website. Update only the files that need changes. "
                "Return the COMPLETE content of the updated files. No explanations."
            )

    def stream_revision(self, user_message: str, current_code: str, history: List[Dict]) -> Generator[str, None, None]:
        """Stream conversational revision from Ollama."""
        system_prompt = self._build_system_prompt(mode="revise")
        
        # Build prompt with history and code context
        full_prompt = f"System: {system_prompt}\n\n"
        for msg in history[-5:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        
        full_prompt += f"\n[CURRENT CODE CONTEXT]\n{current_code}\n\n"
        full_prompt += f"User: {user_message}\nAssistant:"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": self.options
        }

        try:
            with requests.post(self.api_url, json=payload, stream=True, timeout=300) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield chunk.get("response", "")
        except Exception as e:
            logger.error(f"Ollama Revision Stream Error: {str(e)}")
            yield f"\n\n<!-- Error streaming revision: {str(e)} -->"

    # ... (skipping some methods)

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> dict:
        """
        Parse AI output that contains multiple files.
        Supports JSON, '--- filename ---', and '**filename**' formats.
        """
        import re
        import json

        files = {}

        # 1. Try '--- filename ---' or '**filename**' or '### filename'
        sections = re.split(r'(?:---+\s*|(?:\*\*)|(?:###)\s*)([\w\./\-\\]+)(?:\s*---+|(?:\*\*)|(?:\n))', raw_text)
        
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                filename = sections[i].strip()
                content = sections[i+1].strip()
                
                if "." not in filename or len(filename) > 50:
                    continue

                while content.startswith('```') or content.endswith('```'):
                    content = re.sub(r'^```[\w]*\n?', '', content)
                    content = re.sub(r'```$', '', content).strip()
                
                content = re.sub(r'^(?://|#)\s*(?:javascript|jsx|css|html)\n?', '', content, flags=re.IGNORECASE)
                files[filename] = content.strip()
            
            if files:
                return files

        # 2. Try JSON parsing
        try:
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    files_json = {k: v for k, v in data.items() if isinstance(v, str) and "." in k}
                    if files_json:
                        return files_json
        except:
            pass

        # 3. Fallback: treat as index.html
        if raw_text.strip():
            return {"index.html": raw_text.strip()}

        return {}

    @staticmethod
    def merge_files_to_html(files: dict) -> str:
        """Merge multiple React/JSX components into a single previewable HTML."""
        html_content = files.get("index.html", "")
        if not html_content:
            html_content = "<!DOCTYPE html><html><head></head><body><div id='root'></div></body></html>"

        # Remove local script hallucinations
        html_content = re.sub(r'<script\s+src=["\']\.?/?[\w\./\-]+\.(?:jsx|js)["\']\s*>\s*</script>', '', html_content, flags=re.IGNORECASE)
        # Remove tailwind link conflicts
        html_content = re.sub(r'<link\s+rel=["\']stylesheet["\']\s+href=["\'][^"\']*tailwind[^"\']*["\']\s*/?>', '', html_content, flags=re.IGNORECASE)

        cdns = [
            "https://unpkg.com/react@18/umd/react.development.js",
            "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
            "https://unpkg.com/@babel/standalone/babel.min.js",
            "https://cdn.tailwindcss.com"
        ]
        head_tags = ""
        for cdn in cdns:
            if cdn not in html_content:
                head_tags += f'<script src="{cdn}"></script>\n'
        
        if head_tags:
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{head_tags}</head>")
            else:
                html_content = html_content.replace("<body>", f"<head>{head_tags}</head><body>")

        # Gather all JSX/JS content
        js_content = ""
        entry_candidates = ["App.jsx", "App.js", "main.jsx", "main.js"]
        other_files = []
        for filename in files:
            if filename in entry_candidates:
                other_files.insert(0, filename)
            elif filename.endswith((".js", ".jsx")) and filename != "index.html":
                other_files.append(filename)

        for filename in other_files:
            content = files[filename]
            content = re.sub(r"^\s*import\s+[\s\S]*?from\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*import\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*export\s+(default\s+)?", "", content, flags=re.MULTILINE)
            
            if "ReactDOM.render" in content and "createRoot" not in content:
                content = re.sub(
                    r"ReactDOM\.render\s*\(\s*(<[\s\S]+?>)\s*,\s*document\.getElementById\(['\"]root['\"]\)\s*\);?",
                    r"const root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(\1);",
                    content
                )
            
            js_content += f"\n/* --- {filename} --- */\n{content}\n"

        if js_content:
            script_tag = f'<script type="text/babel">\n{js_content}\n</script>'
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{script_tag}</body>")
            else:
                html_content += script_tag

        # Inject CSS
        css_content = ""
        for filename, content in files.items():
            if filename.endswith(".css"):
                css_content += f"\n/* {filename} */\n{content}\n"
        if css_content:
            css_tag = f"<style>{css_content}</style>"
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{css_tag}</head>")
            else:
                html_content = html_content.replace("<body>", f"<head>{css_tag}</head><body>")

        return html_content
