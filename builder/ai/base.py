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
        Parse AI output for file markers: --- filename ---
        Returns: [{"name": str, "content": str}]
        """
        if not raw_text or not isinstance(raw_text, str):
            return []

        files = []

        # Try JSON format first
        try:
            if raw_text.strip().startswith("["):
                parsed = json.loads(raw_text.strip())
                if isinstance(parsed, list):
                    return [
                        {"name": f["name"].lower(), "content": f["content"]}
                        for f in parsed
                        if "name" in f and "content" in f
                    ]
        except json.JSONDecodeError:
            pass

        # Clean text - remove meta tags
        clean_text = raw_text

        # Remove thinking/description tags and their content
        clean_text = re.sub(
            r"<(think|thought|tool_call|description)>.*?</\1>",
            "",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove unclosed tags
        clean_text = re.sub(
            r"<(think|thought|tool_call|description)>.*",
            "",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove step markers
        clean_text = re.sub(
            r"---\s*step:[\s\S]*?---", "", clean_text, flags=re.IGNORECASE
        )

        # Parse file markers: --- filename.ext ---
        marker_pattern = (
            r"(?:\n|^)(?:[-=#]{3,}\s*)([\w./\-\\]+\.[a-zA-Z0-9]{1,10})(?:\s*[-=#]{3,})"
        )
        parts = re.split(marker_pattern, clean_text, flags=re.IGNORECASE)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                filename = parts[i].strip().lower()
                content = parts[i + 1].strip() if i + 1 < len(parts) else ""

                # Skip meta markers
                if any(
                    stop in filename
                    for stop in ["step", "thinking", "thought", "description"]
                ):
                    continue

                # Clean markdown fences
                content = re.sub(r"^```[\w]*\n?", "", content, flags=re.MULTILINE)
                content = re.sub(r"\n?```\s*$", "", content)

                # Clean language annotations
                content = re.sub(
                    r"^(?://|#)\s*(?:javascript|jsx|css|html|typescript|tsx)\n?",
                    "",
                    content,
                    flags=re.IGNORECASE,
                )

                if filename and content:
                    files.append({"name": filename, "content": content.strip()})

        # Fallback: single file
        if not files and clean_text.strip():
            if "<" in clean_text or "{" in clean_text:
                files.append({"name": "index.html", "content": clean_text.strip()})

        return files

    @staticmethod
    def extract_description(raw_text):
        """Extract <description> content."""
        match = re.search(
            r"<description>(.*?)</description>", raw_text, re.DOTALL | re.IGNORECASE
        )
        return match.group(1).strip() if match else ""
