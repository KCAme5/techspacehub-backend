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
    
    def _build_system_prompt(self, project_type="single_file"):
        prompt = (
            "You are an AUTHORITATIVE Senior Frontend Engineer and UI/UX Designer. "
            "Your output will be used to automatically build a high-end production application. "
            
            "CRITICAL RULES:\n"
            "1. NO CONVERSATION: Do NOT provide any intro text or outro. "
            "   START DIRECTLY with the first file separator.\n"
            
            "STRICTLY return ONLY the code sections. DO NOT wrap the entire response in an <html> tag or single block. "
            "Use the markers below to separate distinct files."
        )

        if project_type == "react":
            prompt += (
                "3. REACT FRAMEWORK STRUCTURE (MANDATORY):\n"
                "   - Use Standard React patterns with `import` and `export` statements.\n"
                "   - Folder structure: `src/components/`, `src/pages/`, `src/styles/`.\n"
                "   - REQUIRED FILES: `src/App.jsx`, `src/index.css`, `src/main.jsx`, `public/index.html`.\n"
                "   - In `src/main.jsx`, use: `import App from './App'; ... ReactDOM.createRoot(document.getElementById('root')).render(<App />);`\n"
                "   - Do NOT use `React.useState`; use `import { useState } from 'react';`.\n"
            )
        else:
            prompt += (
                "3. SINGLE BUNDLE STRUCTURE (LEGACY/SIMPLE):\n"
                "   - React, ReactDOM, and Tailwind are global. Do NOT use `import` or `export`.\n"
                "   - Use `React.useState`, `React.useEffect`, etc.\n"
                "   - Files: `index.html`, `App.js`, `styles.css`.\n"
                "   - In App.js, include `ReactDOM.createRoot(document.getElementById('root')).render(<App />);` at the end.\n"
            )

        prompt += (
            "4. VISUAL EXCELLENCE (ROBUST STYLING):\n"
            "   - Use Tailwind CSS for EVERYTHING. Generate rich, premium UI components.\n"
            "   - Layout: Use flexible containers, centering, and generous padding/margins.\n"
            "   - Colors: Use premium palettes (Zinc, Slate, Emerald, Indigo). Use 900/950 for backgrounds.\n"
            "   - Effects: Use `backdrop-blur`, `shadow-2xl`, `rounded-3xl`, and subtle `border`.\n"
            "   - Components: Build distinct sections (Hero, Features, Pricing, Footer) with clear visual hierarchy.\n"
            
            "5. NO PLACEHOLDERS: Use descriptive, high-quality content. For images, use 'https://images.unsplash.com/...' if possible.\n"
            
            "STRICTLY return ONLY the code sections separated by the markers."
        )
        return prompt

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> dict:
        """
        Parses AI output looking for file markers like:
        --- filename ---
        *** # filename ***
        ### File: filename
        """
        files = {}
        # This pattern matches common ways AI denotes a file start
        # Handles ---, ***, ###, File:, etc. cleans up # and quotes.
        marker_pattern = r'(?:\n|^)(?:[#\-\*]{3,}\s*|File:\s*)(?:#\s*|file:?\s*)?["\']?([\w\./\-\\]+)["\']?(?:\s*[#\-\*]{3,}|(?::?\s*\n))'
        
        parts = re.split(marker_pattern, raw_text, flags=re.IGNORECASE)
        
        if len(parts) > 1:
            # First part might be empty or preamble
            for i in range(1, len(parts), 2):
                filename = parts[i].strip().lower()
                content = parts[i+1].strip()
                
                # Clean filename: remove trailing decorators AI might add
                filename = re.sub(r'[:#\*].*$', '', filename).strip()
                if not filename or "." not in filename: continue
                
                # Cleanup markdown fences
                content = re.sub(r'^```[\w]*\n?', '', content, flags=re.MULTILINE)
                content = re.sub(r'```$', '', content.strip()).strip()
                
                # Cleanup language annotations
                content = re.sub(r'^(?://|#)\s*(?:javascript|jsx|css|html|typescript|tsx)\n?', '', content, flags=re.IGNORECASE)
                
                files[filename] = content.strip()
            
            if files: return files

        # Fallback: Markdown blocks
        matches = re.findall(r"```([\w\.]+)\n(.*?)```", raw_text, re.DOTALL)
        for hint, content in matches:
            if "." in hint: files[hint] = content.strip()
        
        if files: return files
        if raw_text.strip(): return {"index.html": raw_text.strip()}
        return {}

    @staticmethod
    def merge_files_to_html(files: dict) -> str:
        """
        Bundles a multi-file project into a single HTML for the preview iframe.
        Inlines CSS and JS to prevent 404 errors.
        """
        # 1. Identify Entry Point
        html_candidates = ["index.html", "public/index.html", "src/index.html"]
        html_content = ""
        for cand in html_candidates:
            if cand in files:
                html_content = files[cand]
                break
        
        if not html_content or ("<div id='root'" not in html_content and '<div id="root"' not in html_content):
            html_content = "<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body><div id='root'></div></body></html>"

        # Ensure head exists
        if "</head>" not in html_content:
            html_content = html_content.replace("<body>", "<head></head><body>")

        # 2. Inline CSS
        # Aggressively find links to local files and replace with <style>
        all_css = ""
        for filename, content in files.items():
            if filename.endswith(".css"):
                all_css += f"\n/* {filename} */\n{content}\n"
                # Strip specific link tags referencing this file
                basename = filename.split("/")[-1]
                pattern = rf'<link\s+[^>]*?href=["\'](?:[^>]*?/)?{re.escape(basename)}["\'][^>]*?/?>'
                html_content = re.sub(pattern, "", html_content, flags=re.IGNORECASE)

        # Remove any leftover link tags that point to relative paths (catch-all)
        html_content = re.sub(r'<link\s+[^>]*?href=["\'](?:(?!\/\/|http).)*?\.css["\'][^>]*?/?>', "", html_content, flags=re.IGNORECASE)
        
        if all_css:
            html_content = html_content.replace("</head>", f"<style>{all_css}</style></head>")

        # 3. Inject CDNs (React, Babel, Tailwind)
        cdns = [
            "https://unpkg.com/react@18/umd/react.development.js",
            "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
            "https://unpkg.com/@babel/standalone/babel.min.js",
            "https://cdn.tailwindcss.com"
        ]
        cdn_scripts = "".join([f'<script src="{cdn}"></script>\n' for cdn in cdns if cdn not in html_content])
        html_content = html_content.replace("</head>", f"{cdn_scripts}</head>")

        # 4. Bundle JS/JSX
        # Remove any local script tags that would 404
        html_content = re.sub(r'<script\s+[^>]*?src=["\'](?:(?!\/\/|http).)*?\.j(?:s|sx|t|tsx)["\'][^>]*?>\s*</script>', '', html_content, flags=re.IGNORECASE)

        js_bundle = ""
        # Sort so that App.jsx / main.jsx are at the bottom (bootstrapping)
        entry_patterns = ["app.jsx", "app.js", "main.jsx", "main.js"]
        sorted_files = sorted(files.keys(), key=lambda x: 1 if any(p in x.lower() for p in entry_patterns) else 0)
        
        for filename in sorted_files:
            if not filename.endswith((".js", ".jsx", ".ts", ".tsx")) or filename == "index.html":
                continue
            
            content = files[filename]
            # Strip imports/exports for Babel preview
            content = re.sub(r"^\s*import\s+[\s\S]*?from\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*import\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*export\s+(?:default\s+)?", "", content, flags=re.MULTILINE)
            content = re.sub(r"ReactDOM\.render\s*\(", "const root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(", content)
            
            js_bundle += f"\n\n/* --- {filename} --- */\n{content}\n"

        if js_bundle:
            script_tag = f'<script type="text/babel">\n{js_bundle}\n</script>'
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{script_tag}</body>")
            else:
                html_content += script_tag

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

