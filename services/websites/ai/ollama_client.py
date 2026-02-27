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

    def __init__(self, model="llama3.1:8b", host="http://localhost:11434"):
        # Host can be overridden via OLLAMA_HOST environment variable
        # For Docker: use host.docker.internal:11434 or the Docker gateway IP (e.g., 10.0.1.1:11434)
        self.host = os.environ.get("OLLAMA_HOST", host)
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.api_url = f"{self.host}/api/generate"

        # Aggressive memory constraints for 16GB RAM CPU-only
        self.options = {
            "num_ctx": 8192,  # Limit context window to save memory
            "num_thread": 2,  # Limit to 2 CPUs to prevent system lockup
            "temperature": 0.2,  # Lower temp for more deterministic code generation
            "top_p": 0.9,
        }

    def _build_system_prompt(self):
        return (
            "You are an expert AI React developer. "
            "Write highly modular, clean, and modern React code using functional components and hooks. "
            "CRITICAL RULES:\n"
            "1. NO IMPORTS: Do NOT use `import ... from ...` or `export ...`. React/ReactDOM are available globally.\n"
            "2. STATE & HOOKS: Use `React.useState`, `React.useEffect`, etc. or destructure from `React`.\n"
            "3. RENDER METHOD: Use `ReactDOM.createRoot(document.getElementById('root')).render(<App />);`.\n"
            "4. STYLING: Use Tailwind CSS ONLY. The CDN is already included. Do NOT add your own <link> for Tailwind.\n"
            "5. OUTPUT FORMAT: Output your project as a series of files using this exact format for EACH file:\n\n"
            "--- FILENAME.EXT ---\n"
            "```language\n"
            "content\n"
            "```\n\n"
            "Required files: index.html, App.jsx, styles.css (if needed).\n"
            "Return ONLY the files. No explanations, no markdown intro."
        )

    def generate_website(self, brief: str, template_id: str = None) -> str:
        """
        Full website generation (Blocking).
        Returns the raw HTML string containing embedded CSS/JS.
        """
        logger.info(f"Ollama Web Gen | Model: {self.model} | Brief: {brief[:50]}...")

        prompt = f"System: {self._build_system_prompt()}\n\nUser: Build a complete, responsive webpage based on this brief: {brief}"
        if template_id:
            prompt += (
                f"\nFollow the design language and structure of template: {template_id}"
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": self.options,
        }

        try:
            # 5-minute timeout because CPU generation of 8K tokens takes time
            response = requests.post(self.api_url, json=payload, timeout=300)
            response.raise_for_status()

            raw_text = response.json().get("response", "")
            
            # Try to parse as multi-file JSON
            files = self.parse_multi_file_output(raw_text)
            if files and "index.html" in files:
                return self.merge_files_to_html(files)
            
            # Fallback to legacy cleaning
            clean_html = re.sub(r'```(?:html|jsx|javascript|js)?\n?|```', '', raw_text, flags=re.IGNORECASE).strip()
            return clean_html

        except requests.exceptions.ReadTimeout:
            logger.error("Ollama generation timed out after 5 minutes.")
            raise Exception(
                "AI took too long to generate the website. Try a simpler prompt."
            )
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Cannot connect to Ollama at {self.host}. Is the container running?"
            )
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
        fast_options["num_predict"] = 2048  # Cap output length for speed

        prompt = f"System: {self._build_system_prompt()}\n\nUser: Build a VERY simple, fast layout mockup using Tailwind (from https://cdn.tailwindcss.com) for this brief: {brief}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": fast_options,
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            raw_text = response.json().get("response", "")
            return re.sub(r"```html\n|```", "", raw_text).strip()
        except Exception as e:
            logger.error(f"Preview Generation Error: {str(e)}")
            return "<html><body><h2>Preview Generation Failed</h2></body></html>"

    def stream_response(self, brief: str):
        """
        Generator for Server-Sent Events (SSE). Streams chunks back to UI.
        """
        if not brief:
            logger.error("stream_response called with empty brief!")
            yield "<!-- Error: No project brief provided -->"
            return

        logger.info(f"Starting stream_response to {self.host} with model {self.model}")

        prompt = f"System: {self._build_system_prompt()}\n\nUser: Build a complete webpage based on this brief: {brief}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self.options,
        }

        try:
            logger.info(f"Sending POST to {self.api_url}")
            with requests.post(
                self.api_url, json=payload, stream=True, timeout=300
            ) as r:
                logger.info(f"Response status: {r.status_code}")
                r.raise_for_status()
                chunk_count = 0
                for line in r.iter_lines():
                    if line:
                        chunk_count += 1
                        try:
                            chunk = json.loads(line)
                            response_text = chunk.get("response", "")
                            if chunk_count <= 5 or chunk_count % 50 == 0:
                                logger.info(
                                    f"Received chunk {chunk_count}: {response_text[:50]}..."
                                )
                            yield response_text
                        except json.JSONDecodeError as je:
                            logger.error(
                                f"JSON decode error on chunk {chunk_count}: {str(je)}"
                            )
                            continue
                logger.info(f"Stream complete. Total chunks: {chunk_count}")
        except requests.exceptions.Timeout:
            logger.error(f"Ollama Streaming Error: Timeout after 300 seconds")
            yield f"\n\n<!-- Error: AI generation timed out -->"
        except requests.exceptions.ConnectionError as ce:
            logger.error(
                f"Ollama Streaming Error: Connection failed to {self.host}: {str(ce)}"
            )
            yield f"\n\n<!-- Error: Cannot connect to AI backend at {self.host} -->"
        except Exception as e:
            logger.error(f"Ollama Streaming Error: {str(e)}")
            yield f"\n\n<!-- Error streaming AI response: {str(e)} -->"

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> dict:
        """
        Parse AI output that contains multiple files.
        Supports both JSON format and '--- filename ---' format.
        """
        import re
        import json

        # 1. Try JSON parsing
        try:
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                cleaned = json_match.group(1)
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    files = {k: v for k, v in data.items() if isinstance(v, str) and "." in k}
                    if files:
                        return files
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Try '--- filename ---' pattern
        files = {}
        # Pattern like: --- filename.ext --- \n ```language \n content \n ```
        sections = re.split(r'---+\s*([\w\./\-\\]+)\s*---+', raw_text)
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                filename = sections[i].strip()
                content = sections[i+1].strip()
                
                # Aggressively remove multiple layers of markdown code block wrappers
                while content.startswith('```') or content.endswith('```'):
                    content = re.sub(r'^```[\w]*\n?', '', content)
                    content = re.sub(r'```$', '', content).strip()
                
                # Remove common header annotations the AI might add
                content = re.sub(r'^(?://|#)\s*(?:javascript|jsx|css|html)\n?', '', content, flags=re.IGNORECASE)
                
                files[filename] = content.strip()
            
            if files:
                return files

        # 3. Fallback: Extract from any markdown code blocks with labels
        pattern = r"```([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, raw_text, re.DOTALL)
        for filename, content in matches:
            filename = filename.strip()
            if "." in filename:
                files[filename] = content.strip()

        return files

    @staticmethod
    def merge_files_to_html(files: dict) -> str:
        """Merge multiple React/JSX components into a single previewable HTML."""
        html_content = files.get("index.html", "")
        
        # Ensure we have a valid HTML structure with a root div
        if not html_content or "<div id='root'" not in html_content and '<div id="root"' not in html_content:
            html_content = "<!DOCTYPE html><html><head></head><body><div id='root'></div></body></html>"

        # Explicitly ensure Babel and React CDNs are present
        cdns = [
            "https://unpkg.com/react@18/umd/react.development.js",
            "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
            "https://unpkg.com/@babel/standalone/babel.min.js",
            "https://cdn.tailwindcss.com"
        ]
        
        head_tags = ""
        for cdn in cdns:
            if cdn not in html_content:
                head_tags += f'    <script src="{cdn}"></script>\n'
        
        if head_tags:
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{head_tags}</head>")
            elif "<body>" in html_content:
                html_content = html_content.replace("<body>", f"<head>\n{head_tags}</head><body>")
            else:
                html_content = f"<html><head>\n{head_tags}</head><body>{html_content}</body></html>"

        # Gather all JSX/JS content
        js_content = ""
        # Prioritize App.jsx/App.js if it exists, then others
        entry_candidates = ["App.jsx", "App.js", "main.jsx", "main.js"]
        other_files = []
        for filename in files:
            if filename in entry_candidates:
                other_files.insert(0, filename)
            elif filename.endswith((".js", ".jsx")) and filename != "index.html":
                other_files.append(filename)

        for filename in other_files:
            content = files[filename]
            # Failsafe: Strip imports and exports that break CDN/Babel preview
            content = re.sub(r"^\s*import\s+[\s\S]*?from\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*import\s+['\"].*?['\"];?\s*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*export\s+(default\s+)?", "", content, flags=re.MULTILINE)
            
            # Failsafe: Convert old ReactDOM.render to createRoot
            if "ReactDOM.render" in content and "createRoot" not in content:
                content = re.sub(
                    r"ReactDOM\.render\s*\(\s*(<[\s\S]+?>)\s*,\s*document\.getElementById\(['\"]root['\"]\)\s*\);?",
                    r"const root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(\1);",
                    content
                )
            
            js_content += f"\n/* --- {filename} --- */\n{content}\n"

        if js_content:
            # Inject as a Babel script
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

    @staticmethod
    def create_zip_archive(files: dict, filename: str = "website.zip") -> io.BytesIO:
        """Package multiple files into a downloadable zip file."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in files.items():
                zf.writestr(fname, content)
        zip_buffer.seek(0)
        return zip_buffer
