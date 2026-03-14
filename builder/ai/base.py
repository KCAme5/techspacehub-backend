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

4. IMAGES — use picsum.photos with descriptive seeds:
   - Format: https://picsum.photos/seed/DESCRIPTIVE-KEYWORD/WIDTH/HEIGHT
   - Fruit website: https://picsum.photos/seed/tropical-fruit/800/500
   - Chicken: https://picsum.photos/seed/farm-chicken/800/500
   - Restaurant: https://picsum.photos/seed/gourmet-food/800/500
   - NEVER use https://picsum.photos/200/300 (too generic, unrelated images)
   - Use different seed words for each image so they show different photos

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

Return ONLY the markers and code. No explanations."""

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

4. IMAGES — use picsum.photos with descriptive seeds:
   - Format: https://picsum.photos/seed/DESCRIPTIVE-KEYWORD/WIDTH/HEIGHT
   - Fruit website: https://picsum.photos/seed/tropical-fruits/800/500
   - Chicken: https://picsum.photos/seed/farm-poultry/800/500
   - Person/team: https://picsum.photos/seed/professional-person/400/400
   - NEVER use https://picsum.photos/200/300 — too generic, shows random unrelated images
   - Use DIFFERENT seed words per image: seed/mango-market, seed/fresh-apples, seed/farm-eggs

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