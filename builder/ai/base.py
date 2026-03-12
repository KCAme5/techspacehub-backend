import re
import logging

logger = logging.getLogger(__name__)

class BaseWebsiteGenerator:
    """Base class for AI website generators with shared parsing and prompt logic."""
    
    def _build_system_prompt(self):
        prompt = (
            "You are an AUTHORITATIVE Senior Frontend Engineer and UI/UX Designer. "
            "Your output will be used to automatically build a high-end production application. "
            
            "CRITICAL RULES:\n"
            "1. NO CONVERSATION: Do NOT provide any intro text or outro. START DIRECTLY with the first file separator.\n"
            "2. DESIGN IDENTITY:\n"
            "   - Use ONLY 'Courier New', monospace for all text elements.\n"
            "   - NO border-radius anywhere (border-radius: 0px !important).\n"
            "   - Use a sharp, brutalist, grid-based layout.\n"
            "   - Primary color: #00f5ff (Forge Cyan).\n"
            
            "STRICTLY return ONLY the code sections. Use the markers below to separate distinct files."
        )

        prompt += (
            "\n3. REACT FRAMEWORK STRUCTURE (MANDATORY):\n"
            "   - Use Standard React patterns with `import` and `export` statements.\n"
            "   - REQUIRED FILES: `src/App.jsx`, `src/index.css`.\n"
        )

        prompt += (
            "\n4. VISUAL EXCELLENCE:\n"
            "   - Use Tailwind CSS for EVERYTHING.\n"
            "   - Use premium palettes (Zinc, Slate). Use 900/950 for backgrounds.\n"
            "   - Focus on sharp borders and high contrast.\n"
        )
        return prompt

    @staticmethod
    def parse_multi_file_output(raw_text: str) -> list:
        """
        Parses AI output looking for file markers like:
        --- filename ---
        Returns a list of dictionaries: [{"name": filename, "content": content}]
        """
        files = []
        marker_pattern = r'(?:\n|^)(?:[#\-\*]{3,}\s*)([\w\./\-\\]+)(?:\s*[#\-\*]{3,})'
        
        parts = re.split(marker_pattern, raw_text, flags=re.IGNORECASE)
        
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                filename = parts[i].strip().lower()
                content = parts[i+1].strip()
                
                # Cleanup markdown fences
                content = re.sub(r'^```[\w]*\n?', '', content, flags=re.MULTILINE)
                content = re.sub(r'```$', '', content.strip()).strip()
                
                # Cleanup language annotations
                content = re.sub(r'^(?://|#)\s*(?:javascript|jsx|css|html|typescript|tsx)\n?', '', content, flags=re.IGNORECASE)
                
                files.append({"name": filename, "content": content.strip()})
        
        return files
