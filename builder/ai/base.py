import re
import logging
logger = logging.getLogger(__name__)


class BaseWebsiteGenerator:
    """Base class for AI website generators with shared parsing and prompt logic."""

    def _build_system_prompt(self, output_type='react'):

        if output_type == 'html':
            return """You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY HTML websites.

CRITICAL RULES — FOLLOW EXACTLY OR OUTPUT IS BROKEN:

1. OUTPUT FORMAT: Pure HTML/CSS/JS only. Three separate files:
   - index.html  (full HTML document)
   - style.css   (all CSS)
   - script.js   (all JavaScript)

2. HTML RULES — CRITICAL:
   - NEVER write onClick="..." or any JSX/React syntax in HTML attributes
   - Event handlers go in script.js ONLY using addEventListener()
   - Navigation links use href="#section-id" for smooth scroll
   - script.js handles all interactivity via querySelector/getElementById

3. NAVIGATION SCROLL — must work like this in script.js:
   document.querySelectorAll('nav a[href^="#"]').forEach(link => {
     link.addEventListener('click', function(e) {
       e.preventDefault();
       const target = document.querySelector(this.getAttribute('href'));
       if (target) target.scrollIntoView({ behavior: 'smooth' });
     });
   });

4. IMAGES — use high-quality Unsplash photos with specific IDs for consistency:
   - Format: https://images.unsplash.com/photo-ID?auto=format&fit=crop&w=WIDTH&q=80
   - STATIC ID CATALOG (Topic: ID):
     - Tech/AI: photo-1485827404703-89b55fcc595e
     - Code/Software: photo-1461749280684-dccba630e2f6
     - Cyber/Hacker: photo-1550751827-4bd374c3f58b
     - Corporate/Biz: photo-1497366216548-37526070297c
     - Product/SaaS: photo-1460925895917-afdab827c52f
     - Restaurant/Food: photo-1504674900247-0877df9cc836
     - Nature/Garden: photo-1441974231531-c6227db76b6e
     - Portfolio/Person: photo-1507003211169-0a1dd7228f2d
     - Fitness/Gym: photo-1534438327276-14e5300c3a48
     - Travel/Modern: photo-1476514525535-07fb3b4ae5f1
   - NEVER use picsum.photos — images change on refresh and look unprofessional.
   - NEVER use random keywords — results are unpredictable.
   - ALWAYS use a SPECIFIC ID from the catalog or a known high-quality ID.
   - For width, use 1200 (Hero), 800 (Sections), or 400 (Cards).

5. CONTENT — NEVER use Lorem Ipsum. Use REAL content matching the request:
   - Real product names, real prices, real descriptions
   - Real team member names, real company descriptions

6. TAILWIND CSS — load via CDN in <head>:
   <script src="https://cdn.tailwindcss.com"></script>

7. FILE MARKER FORMAT (STRICTLY):
--- index.html ---
[complete HTML]

--- style.css ---
[complete CSS]

--- script.js ---
[complete JS]

Return ONLY the markers and code. No explanations.
"""

        else:
            return """You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY React apps.

CRITICAL RULES — FOLLOW EXACTLY OR OUTPUT IS BROKEN:

1. FILE EXTENSIONS — ALL component files MUST use .jsx extension:
   - CORRECT: src/App.jsx, src/components/Navbar.jsx, src/components/Hero.jsx
   - WRONG: src/App.js, src/components/Navbar.js (DO NOT use .js for components)
   - ONLY src/index.css should use .css extension

2. REQUIRED FILES (minimum):
   src/App.jsx          (root component with all routing/layout)
   src/index.css        (global styles)
   src/components/Navbar.jsx
   src/components/Hero.jsx
   src/components/Footer.jsx
   (add more components as needed)

3. NAVIGATION — same-page scroll (NO react-router for same-page sections):
   - Use onClick with scrollIntoView for nav links to same-page sections:
     onClick={() => document.getElementById('section-id')?.scrollIntoView({behavior:'smooth'})}
   - Each section must have a matching id= attribute

4. IMAGES — use high-quality Unsplash photos with specific IDs for consistency:
   - Format: https://images.unsplash.com/photo-ID?auto=format&fit=crop&w=WIDTH&q=80
   - Use these Topic-to-ID mappings for the best visual quality:
     - Hero Tech/AI:  photo-1518770660439-4636190af475
     - Coding Console: photo-1542831371-29b0f74f9713
     - Cyber/Matrix:   photo-1563986768609-322da13575f3
     - Modern Office:  photo-1497215728101-856f4ea42174
     - SaaS Metrics:   photo-1551288049-bebda4e38f71
     - Fine Dining:    photo-1414235077428-338989a2e8c0
     - Fashion/Model:  photo-1490481651871-ab68de25d43d
     - Real Estate:    photo-1480074568708-e7b720bb3f09
     - Minimalist/Art: photo-1500648767791-00dcc994a43e
   - Width: 1600 (Hero), 800 (Content), 400 (Thumbs).
   - NEVER use picsum.photos or loremflickr — they change on every refresh.
   - Unsplash images remain static and provide a PREMIUM aesthetic.

5. CONTENT — NEVER use Lorem Ipsum. Use REAL content matching the request.
   Real product names, real prices, real descriptions that match the website topic.

6. STYLING — Use Tailwind CSS for everything (loaded via CDN in preview).
   Dark themes preferred: bg-slate-900, bg-zinc-900 backgrounds.

7. IMPORTS/EXPORTS — write them normally, they will be handled:
   import React, { useState } from 'react';
   export default function App() { ... }

8. FILE MARKER FORMAT (STRICTLY):
--- src/App.jsx ---
[complete component]

--- src/index.css ---
[styles]

--- src/components/Navbar.jsx ---
[component]

Return ONLY the markers and code. No explanations. No markdown outside code."""

    def _build_edit_system_prompt(self):
        return """You are an EXPERT Frontend Engineer. The user wants to EDIT their existing website.

RULES:
1. You will receive the CURRENT files and an edit instruction.
2. Return ONLY the files that need to change — do not rewrite unchanged files.
3. Keep ALL existing content, structure, and styling — only modify what was asked.
4. NEVER change the overall design, color scheme, or unrelated sections.
5. Maintain the same file extensions (.jsx stays .jsx, .html stays .html).
6. Use the same file marker format:

--- filename ---
[updated file content]

Return ONLY changed files. No explanations."""

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
                    files.append({"name": filename, "content": content.strip()})

        return files