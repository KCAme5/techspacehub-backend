import os
import json
import logging
from groq import Groq
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)


class GroqBuilderClient(BaseWebsiteGenerator):
    """
    Client wrapper for Groq AI for the builder app.
    Yields properly formatted SSE events the Django StreamingHttpResponse
    can send directly to the frontend.
    """

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.environ.get("LLAMA_API_KEY")

        if model == 'llama':
            self.model = "llama-3.3-70b-versatile"
        elif model == 'deepseek':
            # Groq decommissioned deepseek variants — redirect to Llama 3.3
            self.model = "llama-3.3-70b-versatile"
        else:
            self.model = model

        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def _sse(self, payload: dict) -> str:
        """Format a dict as a single SSE line."""
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt: str):
        """
        Yields SSE-formatted strings:
          data: {"progress": "message"}      ← status updates
          data: {"chunk": "token"}           ← raw AI tokens (for streaming overlay)
          data: {"done": true, "files": [...]}  ← final parsed files
          data: {"error": "message"}         ← on failure
        """
        if not self.client:
            logger.error("Groq API key missing.")
            yield self._sse({"error": "Groq API key missing. Set LLAMA_API_KEY in environment."})
            return

        system_prompt = self._build_system_prompt()
        user_prompt = f"Build a complete, responsive React app based on this prompt: {prompt}"

        # ── Step 1: Notify frontend we are starting ───────────────────────────
        yield self._sse({"progress": "Connecting to Llama 3.3..."})

        full_response = ""

        try:
            stream = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=8192,
                stream=True,
            )

            yield self._sse({"progress": "Building structure..."})

            # ── Step 2: Stream tokens to frontend ─────────────────────────────
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_response += token
                    # Send each token as a chunk event so the streaming overlay works
                    yield self._sse({"chunk": token})

            # ── Step 3: Parse the complete response into files ─────────────────
            yield self._sse({"progress": "Parsing files..."})

            files = self.parse_multi_file_output(full_response)

            if not files:
                # Fallback: if parsing found nothing, return the whole thing as
                # a single index.html so the frontend always gets something
                logger.warning("File parsing returned 0 files — using raw fallback")
                files = [{"name": "index.html", "content": full_response.strip()}]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) generated"})

            # ── Step 4: Send the done event with all files ─────────────────────
            yield self._sse({"done": True, "files": files})

        except Exception as e:
            logger.error(f"Groq Streaming Error: {str(e)}")
            yield self._sse({"error": str(e)})