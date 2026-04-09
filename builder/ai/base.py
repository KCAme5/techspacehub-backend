import re
import json
import logging

logger = logging.getLogger(__name__)


class BaseWebsiteGenerator:
    """Base class for AI website generators with robust parsing."""

    SUPPORTED_REACT_DEPENDENCIES = {
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "framer-motion": "^11.11.11",
        "lucide-react": "^0.460.0",
    }
    SUPPORTED_REACT_DEV_DEPENDENCIES = {
        "@vitejs/plugin-react": "^4.3.3",
        "autoprefixer": "^10.4.20",
        "postcss": "^8.4.49",
        "tailwindcss": "^3.4.14",
        "vite": "^5.4.11",
    }
    SUPPORTED_REACT_ROOT_FILES = {
        "package.json",
        "vite.config.js",
        "tailwind.config.js",
        "postcss.config.js",
        "index.html",
    }

    def _build_system_prompt(self, output_type="react"):
        common_protocol = """
=== STRICT OUTPUT PROTOCOL ===
OUTPUT FORMAT (FOLLOW EXACTLY, CHARACTER FOR CHARACTER):
<think>
[Your reasoning and code planning here - NO CODE, ONLY TEXT]
[CRITICAL: You MUST mentally validate the syntax of your generated code here. Check for unmatched brackets, missing imports, and invalid JSX.]
</think>

--- filename.ext ---
[COMPLETE FILE CONTENT - CODE ONLY, NO EXPLANATIONS, NO MARKDOWN BLOCKS]

--- filename2.ext ---
[COMPLETE FILE CONTENT - CODE ONLY]

<description>
Summary of what was built.
</description>

MANDATORY RULES:
1. NO prose, NO explanations, NO "Let me...", NO "I'll...", NO "Here's..." before the first file marker.
2. ONLY output using --- filename --- format. NOTHING else.
3. Each file content section must contain ONLY the actual code. ZERO explanatory text inside code sections.
4. NEVER use markdown code fences (```), NEVER use <tool_call>, NEVER nest <think> tags.
5. filenames must be lowercase. Use . not - in names (src/app.jsx not src-app-jsx).
6. ALL code must be complete and syntactically valid. NO "..." ellipsis, NO omitted sections.
7. Between </think> and the first --- filename ---, output NOTHING. Jump straight to first file marker.
8. If you start explaining something, STOP. Output ONLY code in the file sections.
9. SELF-CORRECTION: Before outputting the final file block, verify that all JSX tags are closed, all imports exist, and that variable names match.
"""
        if output_type == "html":
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY HTML websites.

{common_protocol}

STACK: HTML + CSS + JavaScript only
FILES: 3 total - index.html, style.css, script.js
IMAGES: Use Unsplash IDs like photo-1485827404703-89b55fcc595e
TAILWIND: Load via CDN: <script src="https://cdn.tailwindcss.com"></script>
NO external packages. Everything in these 3 files.

YOUR TURN: Build the website now. Output ONLY:
<think>YOUR_PLAN</think>
--- index.html ---
CODE_HERE
--- style.css ---
CODE_HERE
--- script.js ---
CODE_HERE
<description>Built HTML website</description>
"""
        else:
            return f"""You are an EXPERT Senior Frontend Engineer building PRODUCTION-READY React apps.

{common_protocol}

STACK: Vite + React 18 + Tailwind CSS only
FILE STRUCTURE (EXACT):
  - package.json (npm dependencies: react, react-dom, framer-motion, lucide-react only)
  - vite.config.js
  - tailwind.config.js
  - postcss.config.js
  - index.html
  - src/main.jsx
  - src/index.css
  - src/App.jsx
  - (optional: src/components/*.jsx)

CRITICAL:
1. Use .jsx extensions ALWAYS (not .ts, .tsx, .js)
2. main.jsx MUST: const root = ReactDOM.createRoot(document.getElementById('root')); root.render(<React.StrictMode><App /></React.StrictMode>)
3. Use relevant Unsplash images: Choose appropriate photo IDs or use URLs like https://source.unsplash.com/featured/?{{relevant - keyword}} (e.g., ?restaurant for food sites, ?office for business, ?nature for outdoor). Avoid generic or code-related images.
4. NO Next.js, NO TypeScript, NO CRA, NO remix. ONLY Vite + React.
5. Import from 'lucide-react' for icons. Import from 'framer-motion' for animations.
6. Tailwind classes from CDN config in vite.config.js.

YOUR TURN: Build the React app now. Output ONLY files with --- filename.jsx --- markers. NO explanations in code sections.
"""

    def _build_edit_system_prompt(self):
        return """You are an EXPERT Frontend Engineer editing existing code.

=== STRICT OUTPUT PROTOCOL FOR EDITS ===
<think>
List exactly what you will change:
- File X: change A to B
- File Y: add feature Z
</think>

--- filename.jsx ---
[COMPLETE UPDATED FILE - ONLY CODE, NO EXPLANATIONS]

--- filename2.jsx ---
[COMPLETE UPDATED FILE - ONLY CODE]

<description>
Summary of changes.
</description>

MANDATORY:
1. Return COMPLETE files (not diffs). Include ALL code even unchanged parts.
2. Output ONLY --- filename --- sections. ZERO explanatory text between files.
3. Preserve all working code exactly. Only change what was requested.
4. Do NOT add new npm dependencies. Only: react, react-dom, framer-motion, lucide-react.
5. NO markdown blocks, NO preamble, JUMP TO FIRST FILE after </think>.
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
                f"Return ALL files using --- filename --- format. "
                f"Do not add new dependencies outside react, react-dom, framer-motion, lucide-react."
            )
        return (
            f"Build a complete, production-ready "
            f"{'React app' if output_type == 'react' else 'HTML website'} "
            f"for:\n\n{prompt}\n\n"
            f"Verify all files are complete and syntactically correct. "
            f"For React, target a constrained Vite + React starter with only supported dependencies."
        )

    @staticmethod
    def parse_multi_file_output(raw_text):
        """
        Parse AI output for file markers: --- filename --- or ### filename ###
        Aggressively strips explanatory text and preamble.
        Returns: [{"name": str, "content": str}]
        """
        if not raw_text or not isinstance(raw_text, str):
            return []

        files = []

        # 1. Try JSON format first (some models prefer it)
        try:
            trimmed = raw_text.strip()
            if trimmed.startswith("[") or (
                trimmed.startswith("```json") and "[" in trimmed
            ):
                json_part = trimmed
                if trimmed.startswith("```json"):
                    json_part = re.search(
                        r"```json\s*(\[\s*\{.*\}\s*\])\s*```", trimmed, re.DOTALL
                    )
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

        # 2. Remove thinking/description tags
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

        # 3. Marker patterns (support multiple formats)
        marker_pattern = (
            r"(?:\n|^)[-=#*]{2,}\s*([\w./\-\\]+\.[a-zA-Z0-9]{1,10})\s*(?:[-=#*]{2,})?"
        )

        # 4. If no standard markers found, try markdown code block fallback
        if not re.search(marker_pattern, clean_text):
            code_blocks = re.findall(r"```[\w]*\n(.*?)\n```", clean_text, re.DOTALL)
            for block in code_blocks:
                name_match = re.search(
                    r"(?://|#|/\*)\s*([\w./\-\\]+\.[a-zA-Z0-9]{1,10})", block[:100]
                )
                if name_match:
                    files.append(
                        {"name": name_match.group(1).lower(), "content": block.strip()}
                    )

            if files:
                return files

        # 5. AGGRESSIVE preamble stripping - find first marker
        first_marker = re.search(marker_pattern, clean_text, flags=re.IGNORECASE)
        if first_marker:
            preamble = clean_text[: first_marker.start()]
            # Only keep preamble if it's clearly not explanatory text
            if not BaseWebsiteGenerator._looks_like_explanation(preamble):
                clean_text = preamble + clean_text[first_marker.start() :]
            else:
                # Aggressively strip all preamble
                clean_text = clean_text[first_marker.start() :]

        # 6. Split on markers and extract files
        parts = re.split(marker_pattern, clean_text, flags=re.IGNORECASE)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                filename = parts[i].strip()
                content = parts[i + 1].strip() if i + 1 < len(parts) else ""

                # Skip invalid filenames
                if any(
                    stop in filename.lower()
                    for stop in ["step", "thinking", "thought", "description"]
                ):
                    continue

                # Strip markdown code fences
                content = re.sub(r"^```[\w]*\n?", "", content, flags=re.MULTILINE)
                content = re.sub(r"\n?```\s*$", "", content)

                # AGGRESSIVE: Strip explanatory preamble from inside code sections
                content = BaseWebsiteGenerator._strip_explanation_from_content(content)

                # Standard trailing meta cleanup
                content = BaseWebsiteGenerator._strip_trailing_meta_text(
                    filename, content
                )

                if (
                    filename and content and len(content.strip()) > 10
                ):  # Minimum content length
                    files.append({"name": filename, "content": content})

        # 7. Final Fallback: Single file
        if not files and clean_text.strip():
            if "<html" in clean_text.lower() or "<!DOCTYPE" in clean_text.upper():
                files.append({"name": "index.html", "content": clean_text.strip()})
            elif "export default" in clean_text or "import React" in clean_text:
                files.append({"name": "src/App.jsx", "content": clean_text.strip()})

        return files

    @staticmethod
    def _looks_like_explanation(text):
        """Detect if text looks like explanatory prose rather than code."""
        sample = (text or "").strip()
        if len(sample) < 20:
            return False

        lowered = sample.lower()
        prose_markers = [
            "i'll ",
            "let me ",
            "here's",
            "here is",
            "this is",
            "the following",
            "below",
            "as follows",
            "build a",
            "build an",
            "create a",
            "create an",
            "i've included",
            "i've created",
            "complete production",
            "description:",
        ]

        # High prose marker density = explanation text
        marker_count = sum(1 for marker in prose_markers if marker in lowered)
        code_tokens = sum(
            token in sample
            for token in ["import ", "export ", "function ", "{", "}", "<", "=>"]
        )

        return marker_count >= 2 or (marker_count >= 1 and code_tokens < 3)

    @staticmethod
    def _strip_explanation_from_content(content):
        """Remove explanatory text that got mixed into file content."""
        if not content:
            return content

        lines = content.split("\n")

        # Find the line where actual code likely starts
        code_start_idx = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            # Skip empty lines and stop at first real code
            if (
                stripped
                and not stripped.startswith("//")
                and not stripped.startswith("#")
            ):
                # Check if this looks like a code line
                if any(
                    token in stripped
                    for token in [
                        "import ",
                        "export ",
                        "const ",
                        "let ",
                        "var ",
                        "function ",
                        "{",
                        "class ",
                        "<",
                        "import",
                        "package.json",
                        "{",
                    ]
                ):
                    code_start_idx = idx
                    break
                # If it looks like prose, keep searching
                if BaseWebsiteGenerator._looks_like_explanation(stripped):
                    code_start_idx = idx + 1

        # Rejoin, skipping leading explanation lines
        result = (
            "\n".join(lines[code_start_idx:]).strip() if code_start_idx > 0 else content
        )
        return result

    def ensure_essential_files(self, files, output_type="react"):
        """
        Ensures that essential scaffolding files exist for the project.
        If missing, they are injected with standard defaults.
        """
        if not files:
            return files

        normalized_files = self._normalize_supported_files(
            files, output_type=output_type
        )
        file_map = {f["name"].lower(): f for f in normalized_files}
        files = normalized_files

        if output_type == "react":
            # 1. package.json
            files = self._upsert_file(
                files,
                "package.json",
                self._build_supported_package_json(
                    file_map.get("package.json", {}).get("content", "")
                ),
            )
            file_map = {f["name"].lower(): f for f in files}

            # 2. vite.config.js
            files = self._upsert_file(
                files,
                "vite.config.js",
                self._build_supported_vite_config(),
            )
            file_map = {f["name"].lower(): f for f in files}

            if "tailwind.config.js" not in file_map:
                files.append(
                    {
                        "name": "tailwind.config.js",
                        "content": "/** @type {import('tailwindcss').Config} */\nexport default {\n  content: ['./index.html', './src/**/*.{js,jsx}'],\n  theme: {\n    extend: {},\n  },\n  plugins: [],\n};",
                    }
                )
                file_map["tailwind.config.js"] = {"name": "tailwind.config.js"}

            if "postcss.config.js" not in file_map:
                files.append(
                    {
                        "name": "postcss.config.js",
                        "content": "export default {\n  plugins: {\n    tailwindcss: {},\n    autoprefixer: {},\n  },\n};",
                    }
                )
                file_map["postcss.config.js"] = {"name": "postcss.config.js"}

            # 3. index.html
            if "index.html" not in file_map:
                logger.info("Injecting missing index.html")
                files.append(
                    {
                        "name": "index.html",
                        "content": '<!doctype html>\n<html lang="en">\n  <head>\n    <meta charset="UTF-8" />\n    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n    <title>TechSpace AI Builder</title>\n  </head>\n  <body>\n    <div id="root"></div>\n    <script type="module" src="/src/main.jsx"></script>\n  </body>\n</html>',
                    }
                )

            # 4. src/main.jsx (Entry point)
            if "src/main.jsx" not in file_map:
                logger.info("Injecting missing src/main.jsx")
                files.append(
                    {
                        "name": "src/main.jsx",
                        "content": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App.jsx';\nimport './index.css';\n\nReactDOM.createRoot(document.getElementById('root')).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>\n);",
                    }
                )

            if "src/app.jsx" not in file_map:
                files.append(
                    {
                        "name": "src/App.jsx",
                        "content": 'export default function App() {\n  return (\n    <main className="min-h-screen bg-slate-950 text-slate-50">\n      <section className="mx-auto max-w-5xl px-6 py-24">\n        <p className="text-sm uppercase tracking-[0.3em] text-cyan-300">TechSpace Builder</p>\n        <h1 className="mt-6 text-5xl font-semibold tracking-tight">Your generated site is ready for customization.</h1>\n        <p className="mt-6 max-w-2xl text-lg text-slate-300">Update this starter with your own sections, content, and visual style.</p>\n      </section>\n    </main>\n  );\n}',
                    }
                )

            # 5. src/index.css (Tailwind base)
            if "src/index.css" not in file_map:
                files.append(
                    {
                        "name": "src/index.css",
                        "content": "@tailwind base;\n@tailwind components;\n@tailwind utilities;",
                    }
                )

        return files

    def _normalize_supported_files(self, files, output_type="react"):
        normalized = []
        seen = set()
        for file_data in files:
            name = file_data.get("name", "")
            content = file_data.get("content", "")
            if not name:
                continue
            lowered = name.replace("\\", "/").strip()
            lowered = re.sub(r"^\.\/", "", lowered)
            if output_type == "react":
                if lowered.lower() == "src/main.js":
                    lowered = "src/main.jsx"
                elif lowered.lower() == "src/app.js":
                    lowered = "src/App.jsx"
                if not self._is_supported_react_path(lowered, content):
                    logger.warning("Dropping unsupported generated file: %s", lowered)
                    continue
            key = lowered.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"name": lowered, "content": content})
        return normalized

    @classmethod
    def _is_supported_react_path(cls, path, content):
        normalized = path.lower()
        if normalized in cls.SUPPORTED_REACT_ROOT_FILES:
            return True
        if normalized.startswith("src/") and re.search(
            r"\.(jsx|js|css|html|json|md)$", normalized
        ):
            return True
        if normalized.startswith("public/") and normalized.endswith(".svg"):
            lowered_content = (content or "").lower()
            return "<svg" in lowered_content and "</svg>" in lowered_content
        return False

    @staticmethod
    def _looks_like_summary_text(text):
        sample = (text or "").strip()
        if len(sample) < 40:
            return False

        lowered = sample.lower()
        summary_markers = [
            "complete production-ready",
            "features:",
            "overview:",
            "the app follows",
            "fully responsive design",
            "all files are syntactically correct",
            "production-ready",
        ]
        bullet_count = len(re.findall(r"(?m)^\s*[-*]\s+", sample))
        code_token_count = sum(
            token in sample
            for token in [
                "import ",
                "export ",
                "function ",
                "return (",
                "<div",
                "{",
                "}",
                ";",
            ]
        )

        return (
            bullet_count >= 2 or any(marker in lowered for marker in summary_markers)
        ) and code_token_count < 4

    @classmethod
    def _strip_trailing_meta_text(cls, filename, content):
        cleaned = (content or "").strip()
        lowered_filename = (filename or "").lower()

        if lowered_filename.endswith(".svg"):
            if "<svg" in cleaned.lower() and "</svg>" in cleaned.lower():
                return cleaned[
                    : cleaned.lower().rfind("</svg>") + len("</svg>")
                ].strip()
            return ""

        if lowered_filename.endswith(".html") and "</html>" in cleaned.lower():
            return cleaned[: cleaned.lower().rfind("</html>") + len("</html>")].strip()

        summary_anchor = re.search(
            r"\n{2,}(?=(complete\b|overview\b|features:\b|the app follows\b|all files are\b))",
            cleaned,
            flags=re.IGNORECASE,
        )
        if summary_anchor:
            trailing = cleaned[summary_anchor.start() :].strip()
            if cls._looks_like_summary_text(trailing):
                cleaned = cleaned[: summary_anchor.start()].rstrip()

        if cleaned.endswith("```"):
            cleaned = re.sub(r"\n?```\s*$", "", cleaned).rstrip()
        return cleaned

    def _build_supported_package_json(self, existing_content=""):
        package_data = {}
        if existing_content:
            try:
                package_data = json.loads(existing_content)
            except Exception:
                package_data = {}

        package_data["name"] = package_data.get("name", "techspace-generated-app")
        package_data["private"] = True
        package_data["version"] = "0.0.0"
        package_data["type"] = "module"
        package_data["scripts"] = {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
        }
        package_data["dependencies"] = dict(self.SUPPORTED_REACT_DEPENDENCIES)
        package_data["devDependencies"] = dict(self.SUPPORTED_REACT_DEV_DEPENDENCIES)
        return json.dumps(package_data, indent=2)

    @staticmethod
    def _build_supported_vite_config():
        return (
            "import { defineConfig } from 'vite';\n"
            "import react from '@vitejs/plugin-react';\n\n"
            "const sharedHeaders = {\n"
            "  'Cross-Origin-Opener-Policy': 'same-origin',\n"
            "  'Cross-Origin-Embedder-Policy': 'require-corp',\n"
            "  'Cross-Origin-Resource-Policy': 'cross-origin',\n"
            "};\n\n"
            "export default defineConfig({\n"
            "  plugins: [react()],\n"
            "  server: {\n"
            "    host: '0.0.0.0',\n"
            "    port: 4173,\n"
            "    headers: sharedHeaders,\n"
            "  },\n"
            "  preview: {\n"
            "    host: '0.0.0.0',\n"
            "    port: 4173,\n"
            "    headers: sharedHeaders,\n"
            "  },\n"
            "});"
        )

    @staticmethod
    def _upsert_file(files, name, content):
        updated = False
        for file_data in files:
            if file_data.get("name", "").lower() == name.lower():
                file_data["name"] = name
                file_data["content"] = content
                updated = True
                break
        if not updated:
            files.append({"name": name, "content": content})
        return files

    @staticmethod
    def extract_description(raw_text):
        """Extract <description> content."""
        match = re.search(
            r"<description>(.*?)</description>", raw_text, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        fallback = re.search(
            r"(?is)(complete production-ready.*|overview:.*|features:\s*.*|the app follows.*)$",
            raw_text or "",
        )
        if fallback and BaseWebsiteGenerator._looks_like_summary_text(
            fallback.group(1)
        ):
            return fallback.group(1).strip()

        return ""
