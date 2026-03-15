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
    Handles reasoning models that emit <think>, <thought>, <tool_call>, or
    <description> blocks; all are stripped from the output before it reaches
    the code editor.
    """

    def __init__(self, model="arcee-ai/trinity-large-preview:free"):
        self.api_key  = os.environ.get("OPEN_ROUTER")
        self.model    = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def _sse(self, payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt: str, existing_files=None, output_type: str = 'react'):
        if not self.api_key:
            yield self._sse({"error": "OPEN_ROUTER API key missing. Set OPEN_ROUTER in environment."})
            return

        is_edit = bool(existing_files)
        system  = self._build_edit_system_prompt() if is_edit else self._build_system_prompt(output_type)
        user    = self._build_user_message(prompt, existing_files, output_type, is_edit)

        model_display = self.model.split('/')[-1].replace(':free', '').upper()
        yield self._sse({"progress": f"Connecting to {model_display}..."})

        # ── Regex patterns compiled once ──────────────────────────────────────
        # Detects ANY of the reasoning / tool-call wrappers the model may emit
        META_OPEN  = re.compile(r'<(think|thought|tool_call|description)>', re.IGNORECASE)
        META_CLOSE = re.compile(r'</(think|thought|tool_call|description)>', re.IGNORECASE)
        # File marker: --- filename.ext --- or --- path/to/file.ext ---
        marker_regex = re.compile(
            r'(?:\n|^)(?:[-*#]{3,}\s*)([\w./\-\\]+\.[a-zA-Z]{1,6})(?:\s*[-*#]{3,})',
            re.IGNORECASE
        )

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

            # ── State machine variables ───────────────────────────────────────
            full_response  = ""          # only code content (no reasoning tags)
            in_meta_block  = False       # True when inside any meta tag
            meta_tag_name  = ""          # which tag opened the block
            stream_window  = ""          # last 400 chars for marker detection
            detected_files = set()       # files already reported as progress
            last_step      = ""          # last step marker text
            token_buffer   = ""          # buffer for partial meta tags

            # ── Stream line-by-line using network-driven chunks ───────────────
            # chunk_size=None lets urllib3/TCP decide when to deliver data,
            # avoiding Python-level buffering while staying efficient.
            for raw_line in resp.iter_lines(chunk_size=None):
                if not raw_line:
                    continue

                decoded = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line

                if not decoded.startswith("data: "):
                    continue

                chunk_str = decoded[6:].strip()
                if chunk_str == "[DONE]":
                    break

                try:
                    chunk_data = json.loads(chunk_str)
                    token = (
                        chunk_data.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if not token:
                        continue
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

                # ── Token Accumulation & Meta-tag state machine ───────────────
                # Tokens can be split: "<th", "ink>". We must buffer to detect tags.
                token_buffer += token

                while token_buffer:
                    if in_meta_block:
                        # Look for closing tag
                        close_match = META_CLOSE.search(token_buffer)
                        if close_match:
                            in_meta_block = False
                            if meta_tag_name == "think":
                                yield self._sse({"progress": "Generating code..."})
                            # Send everything before the close tag to thinking stream
                            thinking_content = token_buffer[:close_match.start()]
                            if thinking_content:
                                yield self._sse({"thinking": thinking_content})
                            token_buffer = token_buffer[close_match.end():]
                        else:
                            # Not closed yet.
                            # We can safely stream up to the last '<' to thinking, 
                            # holding back anything after '<' just in case it's the start of </...
                            last_lt = token_buffer.rfind('<')
                            if last_lt == -1:
                                yield self._sse({"thinking": token_buffer})
                                token_buffer = ""
                            elif last_lt > 0:
                                yield self._sse({"thinking": token_buffer[:last_lt]})
                                token_buffer = token_buffer[last_lt:]
                            break # Wait for more chunks to resolve '<'

                    else:
                        # We are IN CODE land. Look for opening tags.
                        open_match = META_OPEN.search(token_buffer)
                        if open_match:
                            before = token_buffer[:open_match.start()]
                            if before:
                                full_response += before
                                stream_window += before
                                yield self._sse({"chunk": before})

                            in_meta_block = True
                            meta_tag_name = open_match.group(1).lower()
                            yield self._sse({"progress": "Model is reasoning..."})
                            token_buffer = token_buffer[open_match.end():]
                        else:
                            # No complete opening tag found.
                            # Check if the buffer ends with a partial tag like '<th'
                            last_lt = token_buffer.rfind('<')
                            if last_lt == -1:
                                # Safe to flush entirely
                                full_response += token_buffer
                                stream_window += token_buffer
                                yield self._sse({"chunk": token_buffer})
                                token_buffer = ""
                            else:
                                # Has a '<'. Flush everything BEFORE it.
                                # Hold back the '<' and everything after it.
                                if last_lt > 0:
                                    safe_chunk = token_buffer[:last_lt]
                                    full_response += safe_chunk
                                    stream_window += safe_chunk
                                    yield self._sse({"chunk": safe_chunk})
                                    token_buffer = token_buffer[last_lt:]
                                break # Wait for more chunks to see if '<' becomes '<think>'

                # ── Keep window bounded ────────────────────────────────────
                if len(stream_window) > 500:
                    stream_window = stream_window[-500:]

                # ── Step marker detection ──────────────────────────────────
                step_m = re.search(r'---\s*step:\s*(.*?)\s*---', stream_window, re.IGNORECASE)
                if step_m:
                    step_text = step_m.group(1).strip()
                    if step_text and step_text != last_step:
                        last_step = step_text
                        yield self._sse({"progress": step_text})

                # ── File marker detection (fallback) ───────────────────────
                file_matches = marker_regex.findall(stream_window)
                if file_matches:
                    latest_file = file_matches[-1].strip().lower()
                    if latest_file not in detected_files:
                        detected_files.add(latest_file)
                        if latest_file not in last_step.lower():
                            action = "Editing" if is_edit else "Writing"
                            yield self._sse({"progress": f"{action} {latest_file}..."})

            # ── Post-stream cleanup ────────────────────────────────────────────
            yield self._sse({"progress": "Finalizing build..."})

            # Final strip of any leftover meta tags and step markers
            full_response = re.sub(
                r'<(?:think|thought|tool_call|description)>.*?</(?:think|thought|tool_call|description)>',
                '', full_response, flags=re.DOTALL | re.IGNORECASE
            )
            full_response = re.sub(r'---\s*step:.*?---', '', full_response, flags=re.IGNORECASE).strip()

            files = self.parse_multi_file_output(full_response)

            if not files:
                files = [{"name": "index.html", "content": full_response or "<!-- Empty response from model -->"}]

            if is_edit and existing_files:
                merged = {f["name"].lower(): f["content"] for f in existing_files}
                for f in files:
                    merged[f["name"].lower()] = f["content"]
                files = [{"name": k, "content": v} for k, v in merged.items()]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) generated"})

            explanation = self.extract_description(full_response)
            if explanation:
                yield self._sse({"explanation": explanation})

            yield self._sse({"done": True, "files": files})

        except requests.exceptions.Timeout:
            yield self._sse({"error": f"Request timed out. {model_display} took too long."})

        except Exception as e:
            logger.error(f"OpenRouter error: {e}", exc_info=True)
            yield self._sse({"error": str(e)})