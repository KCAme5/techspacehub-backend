import os
import re
import json
import logging
import requests
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)


class OpenRouterBuilderClient(BaseWebsiteGenerator):
    """
    OpenRouter client — supports Step 3.5 Flash and other models.
    Handles reasoning models that emit <think>...</think> blocks before code.
    """

    def __init__(self, model="stepfun/step-3.5-flash:free"):
        self.api_key  = os.environ.get("OPEN_ROUTER")
        self.model    = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def _sse(self, payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt: str, existing_files: list = None, output_type: str = 'react'):
        if not self.api_key:
            yield self._sse({"error": "OPEN_ROUTER API key missing. Set OPEN_ROUTER in environment."})
            return

        is_edit = bool(existing_files)
        system  = self._build_edit_system_prompt() if is_edit else self._build_system_prompt(output_type)
        user    = self._build_user_message(prompt, existing_files, output_type, is_edit)

        yield self._sse({"progress": "Connecting to Step 3.5 Flash..."})

        full_response    = ""
        in_think_block   = False  # track <think> reasoning sections
        think_buffer     = ""     # accumulate think content (shown as progress, not as code)

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://techspacehub.co.ke",
                    "X-Title":       "TechSpaceHub Build by AI",
                },
                json={
                    "model":       self.model,
                    "messages":    [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "max_tokens":  16000,
                    "stream":      True,
                    "temperature": 0.3,
                },
                stream=True,
                timeout=(30, 300),
            )

            if not resp.ok:
                error_text = resp.text
                logger.error(f"OpenRouter HTTP error {resp.status_code}: {error_text}")
                yield self._sse({"error": f"OpenRouter error {resp.status_code}: {error_text[:200]}"})
                return

            yield self._sse({"progress": "Building structure..."})

            for line in resp.iter_lines():
                if not line:
                    continue

                decoded = line.decode("utf-8") if isinstance(line, bytes) else line

                if not decoded.startswith("data: "):
                    continue

                chunk_str = decoded[6:]
                if chunk_str.strip() == "[DONE]":
                    break

                try:
                    chunk_data = json.loads(chunk_str)
                    token = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if not token:
                        continue

                    # ── Handle reasoning model <think> blocks ─────────────────
                    # Step 3.5 Flash emits <think>...</think> before the actual code.
                    # We show thinking as progress messages, not as code chunks.
                    if "<think>" in token:
                        in_think_block = True
                        # Split: part before <think> goes to code, rest is thinking
                        parts = token.split("<think>", 1)
                        if parts[0]:
                            full_response += parts[0]
                            yield self._sse({"chunk": parts[0]})
                        think_buffer = parts[1] if len(parts) > 1 else ""
                        yield self._sse({"progress": "Model is reasoning..."})
                        continue

                    if "</think>" in token:
                        in_think_block = False
                        # Part after </think> goes to code
                        parts = token.split("</think>", 1)
                        think_buffer += parts[0]
                        logger.debug(f"Think block: {len(think_buffer)} chars")
                        yield self._sse({"progress": "Building structure..."})
                        if len(parts) > 1 and parts[1]:
                            full_response += parts[1]
                            yield self._sse({"chunk": parts[1]})
                        think_buffer = ""
                        continue

                    if in_think_block:
                        think_buffer += token
                        # Send thinking progress every ~100 chars so user sees activity
                        if len(think_buffer) % 100 < len(token):
                            yield self._sse({"progress": "Model is reasoning..."})
                        continue

                    # ── Normal code token ─────────────────────────────────────
                    full_response += token
                    yield self._sse({"chunk": token})

                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            # ── Log what we got for debugging ─────────────────────────────────
            logger.info(f"OpenRouter raw response: {len(full_response)} chars")
            if len(full_response) < 200:
                logger.warning(f"Very short response from OpenRouter: '{full_response[:200]}'")

            yield self._sse({"progress": "Parsing files..."})

            # ── Strip any remaining <think> blocks from full_response ──────────
            full_response = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()

            files = self.parse_multi_file_output(full_response)

            if not files:
                logger.warning(f"No files parsed. Raw response sample: {full_response[:500]}")
                # Last resort fallback
                files = [{"name": "index.html", "content": full_response or "<!-- Empty response from model -->"}]

            # ── Edit mode: merge changed files into existing ───────────────────
            if is_edit and existing_files:
                merged = {f["name"]: f["content"] for f in existing_files}
                for f in files:
                    merged[f["name"]] = f["content"]
                files = [{"name": k, "content": v} for k, v in merged.items()]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) generated"})
            yield self._sse({"done": True, "files": files})

        except requests.exceptions.Timeout:
            logger.error("OpenRouter request timed out after 180s")
            yield self._sse({"error": "Request timed out. Step 3.5 Flash took too long. Try a shorter prompt or switch to Llama."})

        except Exception as e:
            logger.error(f"OpenRouter error: {e}", exc_info=True)
            yield self._sse({"error": str(e)})