import logging
import os
import json
import re
import io
import zipfile
from groq import Groq

logger = logging.getLogger(__name__)

class BaseWebsiteGenerator:
    """Base class for AI website generators with shared parsing and prompt logic."""
    
    def _build_system_prompt(self):
        return (
            "You are an AUTHORITATIVE Senior Frontend Engineer and UI/UX Designer. "
            "Your output will be used to automatically build a high-end production application. "
            
            "CRITICAL RULES:\n"
            "1. NO CONVERSATION: Do NOT provide any intro text or outro. "
            "   START DIRECTLY with the first file separator.\n"
            
            "2. MULTI-FILE FORMAT: Use these EXACT markers for EVERY file:\n"
            "   --- index.html ---\n"
            "   (code)\n"
            "   --- App.jsx ---\n"
            "   (code)\n"
            "   --- styles.css ---\n"
            "   (code)\n"
            
            "3. NO IMPORTS/EXPORTS: Do NOT use `import` or `export`. "
            "   React, ReactDOM, and Tailwind are global. "
            "   Use `React.useState`, `React.useEffect`, etc.\n"
            
            "4. VISUAL EXCELLENCE (ROBUST STYLING):\n"
            "   - Use Tailwind CSS for EVERYTHING. Do NOT use plain CSS unless absolutely necessary.\n"
            "   - Layout: Use flexible containers, centering, and generous padding/margins.\n"
            "   - Colors: Use premium palettes (Zinc, Slate, Emerald, Indigo). Use 900/950 for backgrounds.\n"
            "   - Effects: Use `backdrop-blur`, `shadow-2xl`, `rounded-3xl`, and subtle `border`. Use `animate-pulse` or `animate-bounce` for micro-interactions.\n"
            "   - Typography: Use bold weights for headers, high tracking for uppercase labels. Use `leading-relaxed` for body text.\n"
            "   - Components: Build distinct sections (Hero, Features, Pricing, Footer) with clear visual hierarchy.\n"
            
            "5. BOOTSTRAPPING: In App.jsx, include this at the VERY end:\n"
            "   ReactDOM.createRoot(document.getElementById('root')).render(<App />);\n"
            
            "6. CLEAN INDEX: Do NOT include <script src='App.jsx'>. I will handle injection.\n"
            
            "STRICTLY return ONLY code sections."
        )

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> dict:
        files = {}
        marker_pattern = r'(?:\n|^)(?:---+\s*|(?:\*\*)|(?:###)\s*|File:\s*)([\w\./\-\\]+)(?:\s*---+|(?:\*\*)|(?::?\s*\n))'
        sections = re.split(marker_pattern, raw_text)
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                filename = sections[i].strip().lower()
                content = sections[i+1].strip()
                filename = re.sub(r'^file:\s*', '', filename)
                if "." not in filename or len(filename) > 50 or " " in filename: continue
                while content.startswith('```') or '```' in content[:100]:
                    content = re.sub(r'^.*?```[\w]*\n?', '', content, count=1, flags=re.DOTALL)
                    content = re.sub(r'```$', '', content.strip()).strip()
                content = re.sub(r'```$', '', content).strip()
                content = re.sub(r'^(?://|#)\s*(?:javascript|jsx|css|html)\n?', '', content, flags=re.IGNORECASE)
                files[filename] = content.strip()
            if files: return files
        try:
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    files_json = {k: v for k, v in data.items() if isinstance(v, str) and "." in k}
                    if files_json: return files_json
        except: pass
        pattern = r"```([\w\.]+)\n(.*?)```"
        matches = re.findall(pattern, raw_text, re.DOTALL)
        for filename_hint, content in matches:
            if "." in filename_hint: files[filename_hint] = content.strip()
        if files: return files
        if raw_text.strip(): return {"index.html": raw_text.strip()}
        return {}

    @staticmethod
    def merge_files_to_html(files: dict) -> str:
        html_content = files.get("index.html", "")
        if not html_content or "<div id='root'" not in html_content and '<div id="root"' not in html_content:
            html_content = "<!DOCTYPE html><html><head></head><body><div id='root'></div></body></html>"
        html_content = re.sub(r'<script\s+src=["\']\.?/?[\w\./\-]+\.(?:jsx|js)["\']\s*>\s*</script>', '', html_content, flags=re.IGNORECASE)
        cdns = [
            "https://unpkg.com/react@18/umd/react.development.js",
            "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
            "https://unpkg.com/@babel/standalone/babel.min.js",
            "https://cdn.tailwindcss.com"
        ]
        html_content = re.sub(r'<link\s+rel=["\']stylesheet["\']\s+href=["\'][^"\']*tailwind[^"\']*["\']\s*/?>', '', html_content, flags=re.IGNORECASE)
        head_tags = "".join([f'    <script src="{cdn}"></script>\n' for cdn in cdns if cdn not in html_content])
        if head_tags:
            if "</head>" in html_content: html_content = html_content.replace("</head>", f"{head_tags}</head>")
            elif "<body>" in html_content: html_content = html_content.replace("<body>", f"<head>\n{head_tags}</head><body>")
            else: html_content = f"<html><head>\n{head_tags}</head><body>{html_content}</body></html>"
        js_content = ""
        entry_candidates = ["app.jsx", "app.js", "main.jsx", "main.js"]
        sorted_files = sorted(files.keys(), key=lambda x: 0 if x in entry_candidates else 1)
        for filename in sorted_files:
            if not filename.endswith((".js", ".jsx")) or filename == "index.html": continue
            content = files[filename]
            content = re.sub(r"^\s*import\s+[\s\S]*?from\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*import\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*export\s+(default\s+)?", "", content, flags=re.MULTILINE)
            if "ReactDOM.render" in content and "createRoot" not in content:
                content = re.sub(r"ReactDOM\.render\s*\(\s*(<[\s\S]+?>)\s*,\s*document\.getElementById\(['\"]root['\"]\)\s*\);?", r"const root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(\1);", content)
            js_content += f"\n/* --- {filename} --- */\n{content}\n"
        if js_content:
            script_tag = f'<script type="text/babel">\n{js_content}\n</script>'
            if "</body>" in html_content: html_content = html_content.replace("</body>", f"{script_tag}</body>")
            else: html_content += script_tag
        css_content = "".join([f"\n/* {f} */\n{c}\n" for f, c in files.items() if f.endswith(".css")])
        if css_content:
            css_tag = f"<style>{css_content}</style>"
            if "</head>" in html_content: html_content = html_content.replace("</head>", f"{css_tag}</head>")
            else: html_content = html_content.replace("<body>", f"<head>{css_tag}</head><body>")
        return html_content

    @staticmethod
    def clean_code_output(raw_text: str) -> str:
        return re.sub(r'```(?:html|jsx|javascript|js)?\n?|```', '', raw_text, flags=re.IGNORECASE).strip()

    @staticmethod
    def create_zip_archive(files: dict, filename: str = "website.zip") -> io.BytesIO:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in files.items(): zf.writestr(fname, content)
        zip_buffer.seek(0)
        return zip_buffer


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

def get_universal_generator():
    from .groq_client import GroqWebsiteGenerator
    return GroqWebsiteGenerator()

def get_universal_conversational_client():
    return GroqConversationalClient()

