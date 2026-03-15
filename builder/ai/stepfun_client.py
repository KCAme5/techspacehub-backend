import os
import re
import json
import logging
import requests
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)


class OpenRouterBuilderClient(BaseWebsiteGenerator):
    """
    OpenRouter client — supports multiple models via OpenRouter aggregator.
    Handles reasoning models that emit <think>...</think> blocks if present.
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

        model_display = self.model.split('/')[-1].replace(':free', '').upper()
        yield self._sse({"progress": f"Connecting to {model_display}..."})

        full_response    = ""
        in_think_block   = False  # track <think> reasoning sections
        think_buffer     = ""     # accumulate think content

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

            yield self._sse({"progress": "Generating code..."})

            marker_regex = re.compile(r'(?:\n|^)(?:[#\-\*]{3,}\s*)([\w\./\-\\]+)(?:\s*[#\-\*]{3,})', re.IGNORECASE)
            
            # To detect markers that might be split across chunks, we keep a small buffer
            stream_window = ""
            detected_files = set()

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
                    if "<think>" in token:
                        in_think_block = True
                        parts = token.split("<think>", 1)
                        if parts[0]:
                            full_response += parts[0]
                            yield self._sse({"chunk": parts[0]})
                            stream_window += parts[0]
                        think_buffer = parts[1] if len(parts) > 1 else ""
                        yield self._sse({"progress": "Model is reasoning..."})
                        continue

                    if "</think>" in token:
                        in_think_block = False
                        parts = token.split("</think>", 1)
                        think_buffer += parts[0]
                        yield self._sse({"progress": "Generating code..."})
                        if len(parts) > 1 and parts[1]:
                            full_response += parts[1]
                            yield self._sse({"chunk": parts[1]})
                            stream_window += parts[1]
                        think_buffer = ""
                        continue

                    if in_think_block:
                        think_buffer += token
                        yield self._sse({"thinking": token})
                        continue

                    # ── Normal code token ─────────────────────────────────────
                    full_response += token
                    yield self._sse({"chunk": token})
                    
                    # ── Step Detection Logic ──────────────────────────────
                    stream_window += token
                    if len(stream_window) > 300: # Keep window enough for step marker
                        stream_window = stream_window[-300:]
                    
                    # Check for explicit steps: --- step: [Description] ---
                    step_match = re.search(r'--- step:\s*(.*?)\s*---', stream_window)
                    if step_match:
                        step_text = step_match.group(1).strip()
                        if not hasattr(self, '_last_step') or self._last_step != step_text:
                            yield self._sse({"progress": step_text})
                            self._last_step = step_text

                    # Fallback marker detection for file writing
                    matches = marker_regex.findall(stream_window)
                    if matches:
                        latest_file = matches[-1].strip().lower()
                        if latest_file not in detected_files:
                            detected_files.add(latest_file)
                            # Only emit if not redundant with an explicit step
                            if not hasattr(self, '_last_step') or latest_file not in self._last_step.lower():
                                action = "Editing" if is_edit else "Writing"
                                yield self._sse({"progress": f"{action} {latest_file}..."})

                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            yield self._sse({"progress": "Finalizing build..."})

            # ── Strip any remaining <think> blocks ──────────
            full_response = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()

            files = self.parse_multi_file_output(full_response)

            if not files:
                files = [{"name": "index.html", "content": full_response or "<!-- Empty response from model -->"}]

            if is_edit and existing_files:
                # Use lowercase keys for deterministic merging
                merged = {f["name"].lower(): f["content"] for f in existing_files}
                for f in files:
                    merged[f["name"].lower()] = f["content"]
                files = [{"name": k, "content": v} for k, v in merged.items()]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) generated"})

            # Extract build description for the frontend
            explanation = self.extract_description(full_response)
            if explanation:
                yield self._sse({"explanation": explanation})
            yield self._sse({"done": True, "files": files})

        except requests.exceptions.Timeout:
            yield self._sse({"error": f"Request timed out. {model_display} took too long."})

        except Exception as e:
            logger.error(f"OpenRouter error: {e}", exc_info=True)
            yield self._sse({"error": str(e)})