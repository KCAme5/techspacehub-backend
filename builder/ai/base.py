import re
import json
import logging

logger = logging.getLogger(__name__)


class BaseWebsiteGenerator:
    """Base class for AI website generators with robust parsing."""

    def _build_system_prompt(self, output_type="react"):
        common_protocol = """
STRICT PROTOCOL - FOLLOW EXACTLY:
1. FIRST: Write your reasoning inside <think>...</think> tags ONLY. NO code inside think tags.
2. AFTER the closing </think> tag, output ALL file code using this EXACT format:
   --- filename ---
   [complete file content here]
   
3. END with a summary inside <description>...</description> tags.
4. Use lowercase for all filenames.
5. NEVER use markdown code blocks (```) around file markers.
6. NEVER use <tool_call> or nested <think> tags.
7. NEVER put code inside <think> blocks — code MUST come after </think>.
8. Ensure ALL code is complete, valid, and production-ready.
"""
        if output_type == "html":
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY HTML websites.
{common_protocol}

CRITICAL RULES:
1. OUTPUT: Three files only - index.html, style.css, script.js
2. IMAGES: Use Unsplash IDs: photo-1485827404703-89b55fcc595e, photo-1461749280684-dccba630e2f6
3. TAILWIND: Load via CDN: <script src="https://cdn.tailwindcss.com"></script>
4. NO EXTERNAL DEPENDENCIES - everything in the 3 files
5. VALIDATE all HTML tags are closed, all CSS braces match
"""
        else:
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY React apps.
{common_protocol}

CRITICAL RULES:
1. FILE EXTENSIONS: ALL components MUST use .jsx (NOT .js)
2. REQUIRED FILES: src/App.jsx, src/index.css, src/main.jsx
3. IMAGES: Use Unsplash IDs: photo-1518770660439-4636190af475, photo-1542831371-29b0f74f9713
4. STYLING: Use Tailwind CSS classes, dark themes preferred
5. VALIDATION: Check ALL JSX tags closed, ALL imports valid, NO incomplete code
6. main.jsx MUST use: ReactDOM.createRoot(document.getElementById('root'))
"""

    def _build_edit_system_prompt(self):
        return """You are an EXPERT Frontend Engineer editing existing code.

STRICT PROTOCOL:
1. START with <think>...</think> tags describing your changes.
2. Return ONLY files that need changes using: --- filename ---
3. Return COMPLETE file content, not just changes.
4. END with <description>...</description> tags.
5. NEVER use markdown code blocks around markers.
6. Preserve all working code exactly.
"""

    def _build_user_message(self, prompt, existing_files, output_type, is_edit):
        if is_edit and existing_files:
            files_context = "\n\n".join(
                [f"--- {f['name']} ---\n{f['content']}" for f in existing_files]
            )
            return (
                f"CURRENT FILES:\n\n{files_context}\n\n"
                f"EDIT REQUEST: {prompt}\n\n"
                f"Make MINIMAL changes. Preserve working code. "
                f"Return ALL files using --- filename --- format."
            )
        return (
            f"Build a complete, production-ready "
            f"{'React app' if output_type == 'react' else 'HTML website'} "
            f"for:\n\n{prompt}\n\n"
            f"Verify all files are complete and syntactically correct."
        )

    @staticmethod
    def parse_multi_file_output(raw_text):
        """
        Parse AI output for file markers: --- filename --- or ### filename ###
        Returns: [{"name": str, "content": str}]
        """
        if not raw_text or not isinstance(raw_text, str):
            return []

        files = []

        # 1. Try JSON format first (some models prefer it)
        try:
            trimmed = raw_text.strip()
            if trimmed.startswith("[") or (trimmed.startswith("```json") and "[" in trimmed):
                json_part = trimmed
                if trimmed.startswith("```json"):
                    json_part = re.search(r"```json\s*(\[\s*\{.*\}\s*\])\s*```", trimmed, re.DOTALL)
                    json_part = json_part.group(1) if json_part else trimmed
                
                parsed = json.loads(json_part)
                if isinstance(parsed, list):
                    return [
                        {"name": f["name"].lower(), "content": f["content"]}
                        for f in parsed
                        if "name" in f and "content" in f
                    ]
        except Exception:
            pass

        # 2. Clean text - remove thinking/description tags
        clean_text = raw_text
        clean_text = re.sub(
            r"<(think|thought|tool_call|description)>.*?</\1>",
            "",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean_text = re.sub(
            r"<(think|thought|tool_call|description)>.*",
            "",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # 3. Handle models that use Markdown headers instead of dashes
        # e.g. ### src/App.jsx
        # Use a regex that finds --- filename --- or ### filename ### or **filename**
        marker_pattern = (
            r"(?:\n|^)(?:[-=#*]{2,}\s*)([\w./\-\\]+\.[a-zA-Z0-9]{1,10})(?:\s*[-=#*]{2,})"
        )
        
        # 4. Fallback for models that use markdown code blocks WITH filename as first line or comment
        # e.g. ```jsx\n// src/App.jsx\n...```
        if not re.search(marker_pattern, clean_text):
            # Try to find ```blocks with potential filenames inside
            code_blocks = re.findall(r"```[\w]*\n(.*?)\n```", clean_text, re.DOTALL)
            for block in code_blocks:
                # Look for filename in first few lines as a comment
                name_match = re.search(r"(?://|#|/\*)\s*([\w./\-\\]+\.[a-zA-Z0-9]{1,10})", block[:100])
                if name_match:
                    files.append({"name": name_match.group(1).lower(), "content": block.strip()})
            
            if files: return files

        # 5. Standard Marker Parsing
        parts = re.split(marker_pattern, clean_text, flags=re.IGNORECASE)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                filename = parts[i].strip()
                content = parts[i + 1].strip() if i + 1 < len(parts) else ""

                if any(stop in filename for stop in ["step", "thinking", "thought", "description"]):
                    continue

                # Clean markdown fences inside the content
                content = re.sub(r"^```[\w]*\n?", "", content, flags=re.MULTILINE)
                content = re.sub(r"\n?```\s*$", "", content)
                
                # Strip leading/trailing notes if any
                content = content.split("---")[0].split("###")[0].strip()

                if filename and content:
                    files.append({"name": filename, "content": content})

        # 6. Final Fallback: Single file (usually HTML or React App.jsx)
        if not files and clean_text.strip():
            if "<html" in clean_text.lower() or "<!DOCTYPE" in clean_text.upper():
                files.append({"name": "index.html", "content": clean_text.strip()})
            elif "export default" in clean_text or "import React" in clean_text:
                files.append({"name": "src/App.jsx", "content": clean_text.strip()})

        return files

    def ensure_essential_files(self, files, output_type="react"):
        """
        Ensures that essential scaffolding files exist for the project.
        If missing, they are injected with standard defaults.
        """
        if not files:
            return files

        file_map = {f["name"].lower(): f for f in files}

        if output_type == "react":
            # 1. package.json
            if "package.json" not in file_map:
                logger.info("Injecting missing package.json")
                files.append({
                    "name": "package.json",
                    "content": json.dumps({
                        "name": "techspace-generated-app",
                        "private": True,
                        "version": "0.0.0",
                        "type": "module",
                        "scripts": {
                            "dev": "vite",
                            "build": "vite build",
                            "preview": "vite preview"
                        },
                        "dependencies": {
                            "react": "^18.3.1",
                            "react-dom": "^18.3.1",
                            "lucide-react": "^0.460.0",
                            "framer-motion": "^11.11.11"
                        },
                        "devDependencies": {
                            "@vitejs/plugin-react": "^4.3.3",
                            "autoprefixer": "^10.4.20",
                            "postcss": "^8.4.49",
                            "tailwindcss": "^3.4.14",
                            "vite": "^5.4.11"
                        }
                    }, indent=2)
                })

            # 2. vite.config.js
            if "vite.config.js" not in file_map:
                logger.info("Injecting missing vite.config.js")
                files.append({
                    "name": "vite.config.js",
                    "content": "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\n\nexport default defineConfig({\n  plugins: [react()],\n});"
                })

            # 3. index.html
            if "index.html" not in file_map:
                logger.info("Injecting missing index.html")
                files.append({
                    "name": "index.html",
                    "content": "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"UTF-8\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n    <title>TechSpace AI Builder</title>\n    <script src=\"https://cdn.tailwindcss.com\"></script>\n  </head>\n  <body>\n    <div id=\"root\"></div>\n    <script type=\"module\" src=\"/src/main.jsx\"></script>\n  </body>\n</html>"
                })

            # 4. src/main.jsx (Entry point)
            if "src/main.jsx" not in file_map:
                logger.info("Injecting missing src/main.jsx")
                files.append({
                    "name": "src/main.jsx",
                    "content": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App.jsx';\nimport './index.css';\n\nReactDOM.createRoot(document.getElementById('root')).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>\n);"
                })
            
            # 5. src/index.css (Tailwind base)
            if "src/index.css" not in file_map:
                 files.append({
                    "name": "src/index.css",
                    "content": "@tailwind base;\n@tailwind components;\n@tailwind utilities;"
                })

        return files

    @staticmethod
    def extract_description(raw_text):
        """Extract <description> content."""
        match = re.search(
            r"<description>(.*?)</description>", raw_text, re.DOTALL | re.IGNORECASE
        )
        return match.group(1).strip() if match else ""
