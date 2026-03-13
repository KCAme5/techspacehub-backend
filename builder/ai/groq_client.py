import os
import json
import logging
from groq import Groq
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)


class GroqBuilderClient(BaseWebsiteGenerator):
    """
    Client wrapper for Groq AI for the builder app.
    Yields properly formatted SSE events for Django StreamingHttpResponse.
    Supports both fresh generation and edit/continuation mode.
    """

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.environ.get("LLAMA_API_KEY")

        if model == 'llama':
            self.model = "llama-3.3-70b-versatile"
        elif model == 'deepseek':
            self.model = "llama-3.3-70b-versatile"
        else:
            self.model = model

        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def _sse(self, payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt: str, existing_files: list = None, output_type: str = 'react'):
        """
        Yields SSE-formatted strings.

        Args:
            prompt:         The user's instruction
            existing_files: List of {"name": str, "content": str} from previous generation.
                            If provided → EDIT mode (keep context, modify only what's asked)
                            If None    → FRESH generation mode
            output_type:    'react' or 'html'
        """
        if not self.client:
            yield self._sse({"error": "Groq API key missing. Set LLAMA_API_KEY in environment."})
            return

        is_edit_mode = bool(existing_files)

        if is_edit_mode:
            system_prompt = self._build_edit_system_prompt()
            files_context = "\n\n".join([
                f"--- {f['name']} ---\n{f['content']}"
                for f in existing_files
            ])
            user_message = (
                f"Here are the CURRENT website files:\n\n"
                f"{files_context}\n\n"
                f"USER EDIT REQUEST: {prompt}\n\n"
                f"Return ONLY the files that need to change using the --- filename --- marker format."
            )
            yield self._sse({"progress": "Analyzing existing code..."})
        else:
            system_prompt = self._build_system_prompt(output_type=output_type)
            user_message = (
                f"Build a complete, production-ready {'React app' if output_type == 'react' else 'HTML website'} "
                f"for the following request:\n\n{prompt}"
            )
            yield self._sse({"progress": f"Connecting to {self.model}..."})

        full_response = ""

        try:
            stream = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=8192,
                stream=True,
            )

            yield self._sse({"progress": "Building structure..." if not is_edit_mode else "Applying edits..."})

            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_response += token
                    yield self._sse({"chunk": token})

            yield self._sse({"progress": "Parsing files..."})

            new_files = self.parse_multi_file_output(full_response)

            if not new_files:
                logger.warning("File parsing returned 0 files — using raw fallback")
                new_files = [{"name": "index.html", "content": full_response.strip()}]

            # In edit mode: merge changed files into existing files
            if is_edit_mode and existing_files:
                merged = {f['name']: f['content'] for f in existing_files}
                for f in new_files:
                    merged[f['name']] = f['content']
                final_files = [{"name": k, "content": v} for k, v in merged.items()]
                yield self._sse({"progress": f"Updated {len(new_files)} file(s)"})
            else:
                final_files = new_files
                yield self._sse({"progress": f"Complete — {len(final_files)} file(s) generated"})

            yield self._sse({"done": True, "files": final_files})

        except Exception as e:
            logger.error(f"Groq Streaming Error: {str(e)}")
            yield self._sse({"error": str(e)})