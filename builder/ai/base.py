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
   - Restaurant: https://loremflickr.com/800/500/restaurant,food
   - NEVER use picsum.photos — images are random, change on every refresh, unprofessional
   - NEVER use source.unsplash.com — it is shut down and returns 404
   - Use loremflickr.com ONLY — format: https://loremflickr.com/WIDTH/HEIGHT/keyword1,keyword2
   - Use SPECIFIC keywords matching the website topic:
     Chicken shop:   https://loremflickr.com/800/500/chicken,farm
     Fruit market:   https://loremflickr.com/800/400/fruit,market
     Cybersecurity:  https://loremflickr.com/800/500/cybersecurity,technology
     Restaurant:     https://loremflickr.com/800/500/restaurant,food
     Portfolio hero: https://loremflickr.com/1200/600/developer,coding
     Team member:    https://loremflickr.com/400/400/person,professional
     Product item:   https://loremflickr.com/400/300/product,shop
   - Add a unique number at end to get different images: /800/500/fruit,market/1 /2 /3

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

4. IMAGES — use loremflickr.com for ALL images:
   - Format: https://loremflickr.com/WIDTH/HEIGHT/keyword1,keyword2
   - NEVER use picsum.photos — images are random, change on every page refresh, look unprofessional
   - NEVER use source.unsplash.com — it is permanently shut down
   - NEVER use images.unsplash.com — requires auth, breaks in preview
   - loremflickr returns topic-specific photos that stay consistent and relevant:
     Chicken/poultry shop: https://loremflickr.com/800/500/chicken,poultry/1
     Fruit/produce:        https://loremflickr.com/800/400/fruit,tropical/1
     Cybersecurity:        https://loremflickr.com/800/500/cybersecurity,hacker/1
     Restaurant/food:      https://loremflickr.com/800/500/restaurant,food/1
     Developer portfolio:  https://loremflickr.com/1200/600/developer,coding/1
     Team/people:          https://loremflickr.com/400/400/person,professional/1
     Product cards:        https://loremflickr.com/400/300/product,shop/1
     Hero background:      https://loremflickr.com/1600/900/TOPIC,website/1
   - Increment the trailing number /1 /2 /3 for different images of the same topic

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