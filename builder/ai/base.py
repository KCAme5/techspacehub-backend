import re
import logging
logger = logging.getLogger(__name__)


class BaseWebsiteGenerator:
    """Base class for AI website generators with shared parsing and prompt logic."""

    def _build_system_prompt(self, output_type='react'):
        return f"""You are an EXPERT Senior Frontend Engineer and UI/UX Designer building PRODUCTION-READY websites.

CRITICAL CONTENT RULES — FOLLOW EXACTLY:
1. NEVER use "Lorem ipsum" or placeholder text. EVER.
2. Use REAL, SPECIFIC, MEANINGFUL content that matches the user's request.
   - If user asks for a chicken selling website: use real product names like "Farm Fresh Whole Chicken - KES 850", "Organic Free-Range Eggs - KES 320/tray"
   - If user asks for a portfolio: use real-sounding skill names, project titles, bio text
   - If user asks for a restaurant: use real menu items with real prices and descriptions
3. Use REAL image URLs from https://source.unsplash.com — format: https://source.unsplash.com/800x600/?[keyword]
   - Chicken website: https://source.unsplash.com/800x600/?chicken,farm
   - Portfolio: https://source.unsplash.com/800x600/?developer,coding
   - Restaurant: https://source.unsplash.com/800x600/?food,restaurant
4. Every section must have COMPLETE content — real headings, real descriptions, real data.

TECHNICAL REQUIREMENTS:
{"React with Tailwind CSS. Multi-component architecture." if output_type == 'react' else "Pure HTML/CSS/JS. Single file or split files."}
- Use Tailwind CSS for ALL styling (loaded via CDN in preview)
- Dark theme preferred: bg-slate-900, bg-zinc-900, or bg-gray-900 backgrounds
- High contrast text, sharp borders, modern spacing
- Fully responsive (mobile-first)
- Interactive elements must work: buttons have onClick, forms have handlers, nav links scroll to sections

NAVIGATION & SCROLLING RULES (CRITICAL):
- Nav links MUST use smooth scroll to sections: onClick={{() => document.getElementById('section-id')?.scrollIntoView({{behavior:'smooth'}})}}
- Every nav item must correspond to a real section with a matching id= attribute
- Do NOT use react-router Link for same-page navigation — use onClick scroll instead
- External page links should use href="#" with preventDefault

FILE MARKER FORMAT (STRICTLY FOLLOW):
--- filename ---
[complete file content]

Required files for React: src/App.jsx, src/index.css
Optional but encouraged: src/components/Navbar.jsx, src/components/Hero.jsx, etc.

IMPORTANT: Return ONLY the file markers and code. No explanations. No conversation. No markdown outside of code blocks."""

    def _build_edit_system_prompt(self):
        return """You are an EXPERT Frontend Engineer. The user wants to EDIT their existing website.

RULES:
1. You will receive the CURRENT files and an edit instruction.
2. Return ONLY the files that need to change — do not rewrite unchanged files.
3. Keep ALL existing content, structure, and styling — only modify what was asked.
4. NEVER change the overall design, color scheme, or unrelated sections.
5. Use the same file marker format:

--- filename ---
[updated file content]

Return ONLY changed files. No explanations."""

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
                    files.append({"name": filename, "content": content.strip()})

        return files