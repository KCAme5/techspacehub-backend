import re
import logging
logger = logging.getLogger(__name__)


class BaseWebsiteGenerator:
    """Base class for AI website generators with shared parsing and prompt logic."""

    def _build_system_prompt(self, output_type='react'):
        common_protocol = """
STRICT PROTOCOL:
1. START with your reasoning inside <think>...</think> tags.
2. For EVERY logical section or file you start, emit a marker: --- step: [Short Description] ---
3. Use the file marker format below for code:
   --- filename ---
   [content]

4. END your response with a summary inside <description>...</description> tags. Describe exactly what you built.
5. Use lowercase for all filenames.
6. Return ONLY markers, tags, and code. No markdown fences around markers.
"""
        if output_type == 'html':
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY HTML websites.
{common_protocol}
CRITICAL RULES — FOLLOW EXACTLY OR OUTPUT IS BROKEN:

1. OUTPUT FORMAT: Pure HTML/CSS/JS only. Three separate files:
   - index.html, style.css, script.js

2. IMAGES: Use high-quality Unsplash photos from these IDs:
   photo-1485827404703-89b55fcc595e (AI), photo-1461749280684-dccba630e2f6 (Code), photo-1497366216548-37526070297c (Corporate)

3. TAILWIND CSS: Load via CDN in <head>:
   <script src="https://cdn.tailwindcss.com"></script>
"""

        else:
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY React apps.
{common_protocol}
CRITICAL RULES — FOLLOW EXACTLY OR OUTPUT IS BROKEN:

1. FILE EXTENSIONS: ALL component files MUST use .jsx extension.
2. REQUIRED FILES: src/App.jsx, src/index.css, etc.
3. IMAGES: Use high-quality Unsplash IDs:
   photo-1518770660439-4636190af475 (Tech), photo-1542831371-29b0f74f9713 (Code), photo-1551288049-bebda4e38f71 (Metrics)

4. STYLING: Use Tailwind CSS for everything. Dark themes preferred.
"""
    def _build_edit_system_prompt(self):
        return """You are an EXPERT Frontend Engineer. The user wants to EDIT their existing website.

STRICT PROTOCOL:
1. START with your reasoning inside <think>...</think> tags.
2. For EVERY logical section or file you start, emit a marker: --- step: [Short Description] ---
3. Return ONLY the files that need to change.
4. For modified files, return the FULL updated content.
5. END your response with a summary inside <description>...</description> tags.
6. Use the file marker format: --- filename ---
7. Standardize all filenames to lowercase.
8. Return ONLY markers, tags, and code. No markdown fences."""

    def _build_user_message(self, prompt: str, existing_files: list, output_type: str, is_edit: bool) -> str:
        """Build the user message — shared by all AI clients."""
        if is_edit and existing_files:
            files_context = "\n\n".join([
                f"--- {f['name']} ---\n{f['content']}"
                for f in existing_files
            ])
            return (
                f"Here are the CURRENT website files:\n\n"
                f"{files_context}\n\n"
                f"USER EDIT REQUEST: {prompt}\n\n"
                f"Return ONLY the files that need to change using the --- filename --- marker format."
            )
        else:
            return (
                f"Build a complete, production-ready "
                f"{'React app' if output_type == 'react' else 'HTML website'} "
                f"for the following request:\n\n{prompt}"
            )

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> list:
        """
        Parses AI output looking for file markers like:
        --- filename ---
        Returns a list of dicts: [{"name": filename, "content": content}]
        """
        files = []
        marker_pattern = r'(?:\n|^)(?:[#\-\*]{3,}\s*)([\w\./\-\\]+)(?:\s*[#\-\*]{3,})'

        parts = re.split(marker_pattern, raw_text, flags=re.IGNORECASE)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                filename = parts[i].strip().lower()
                content  = parts[i + 1].strip() if i + 1 < len(parts) else ''

                # Cleanup markdown fences
                content = re.sub(r'^```[\w]*\n?', '', content, flags=re.MULTILINE)
                content = re.sub(r'```$', '', content.strip()).strip()

                # Cleanup language annotations
                content = re.sub(
                    r'^(?://|#)\s*(?:javascript|jsx|css|html|typescript|tsx)\n?',
                    '', content, flags=re.IGNORECASE
                )

                if filename and content:
                    # Standardize all filenames to lowercase to prevent duplication (e.g., App.jsx vs app.jsx)
                    filename = filename.lower()
                    files.append({"name": filename, "content": content.strip()})

        return files

    @staticmethod
    def extract_description(raw_text: str) -> str:
        """Extract content inside <description>...</description> tags."""
        match = re.search(r'<description>(.*?)</description>', raw_text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""