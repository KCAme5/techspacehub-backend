import os
import re
import json
import logging
import requests
from .base import BaseWebsiteGenerator

logger = logging.getLogger(__name__)


class OpenRouterBuilderClient(BaseWebsiteGenerator):
    """
    OpenRouter client with proper real-time SSE streaming.
    FIXED: Immediate token delivery, proper tag handling, no buffering.
    """

    def __init__(self, model="arcee-ai/trinity-large-preview:free"):
        self.api_key = os.environ.get("OPEN_ROUTER")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def _sse(self, payload):
        """Format as SSE data line."""
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt, existing_files=None, output_type="react", suppress_done=False):
        """
        Stream generation with real-time token delivery.
        Yields SSE events immediately as they arrive from API.
        """
        if not self.api_key:
            yield self._sse({"error": "OPEN_ROUTER API key missing"})
            return

        is_edit = bool(existing_files)
        system = (
            self._build_edit_system_prompt()
            if is_edit
            else self._build_system_prompt(output_type)
        )
        user = self._build_user_message(prompt, existing_files, output_type, is_edit)

        model_display = self.model.split("/")[-1].replace(":free", "").upper()
        yield self._sse({"progress": f"Initializing {model_display}..."})

        # Regex patterns
        META_TAGS = re.compile(
            r"<(/?)(think|thought|tool_call|description)>", re.IGNORECASE
        )
        FILE_MARKER = re.compile(
            r"(?:\n|^)(?:[-=#]{3,}\s*)([\w./\-\\]+\.[a-zA-Z0-9]{1,10})(?:\s*[-=#]{3,})",
            re.IGNORECASE,
        )

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://techspacehub.co.ke",
                    "X-Title": "TechSpaceHub",
                    "Accept": "text/event-stream",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 16000,
                    "stream": True,
                    "temperature": 0.3,
                },
                stream=True,
                timeout=(30, 300),
            )

            if not resp.ok:
                error_text = resp.text[:500]
                logger.error(f"OpenRouter HTTP {resp.status_code}: {error_text}")
                yield self._sse(
                    {"error": f"API Error {resp.status_code}: {error_text}"}
                )
                return

            yield self._sse({"progress": "Connected - streaming..."})

            # Stream processing state
            full_response = []        # Collects non-thinking code chunks
            thinking_response = []    # Collects content from inside think blocks
            in_think_block = False
            incomplete_buffer = ""
            detected_files = set()
            last_progress = ""

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                line = line.strip()
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    token = (
                        data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    )
                    if not token:
                        continue
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

                # Handle incomplete tags from previous chunk
                if incomplete_buffer:
                    token = incomplete_buffer + token
                    incomplete_buffer = ""

                # Process token
                pos = 0
                while pos < len(token):
                    if in_think_block:
                        # Look for closing tag
                        close_match = META_TAGS.search(token[pos:])
                        if close_match and close_match.group(1) == "/":
                            # Found closing tag
                            think_content = token[pos : pos + close_match.start()]
                            if think_content:
                                thinking_response.append(think_content)
                                yield self._sse({"thinking": think_content})

                            in_think_block = False
                            pos += close_match.end()
                            yield self._sse({"progress": "Writing code..."})
                        else:
                            # Check for partial closing tag at end
                            remaining = token[pos:]
                            partial_close = remaining.rfind("</")
                            if (
                                partial_close != -1
                                and len(remaining) - partial_close < 10
                            ):
                                incomplete_buffer = remaining[partial_close:]
                                if partial_close > 0:
                                    thinking_response.append(remaining[:partial_close])
                                    yield self._sse(
                                        {"thinking": remaining[:partial_close]}
                                    )
                            else:
                                thinking_response.append(remaining)
                                yield self._sse({"thinking": remaining})
                            break
                    else:
                        # Look for opening tag
                        open_match = META_TAGS.search(token[pos:])
                        if open_match and open_match.group(1) == "":
                            # Found opening tag
                            before_tag = token[pos : pos + open_match.start()]
                            if before_tag:
                                full_response.append(before_tag)
                                yield self._sse({"chunk": before_tag})

                            in_think_block = True
                            pos += open_match.end()
                            yield self._sse({"progress": "AI thinking..."})
                        else:
                            # Check for partial opening tag
                            remaining = token[pos:]
                            partial_open = remaining.rfind("<")
                            if (
                                partial_open != -1
                                and len(remaining) - partial_open < 10
                            ):
                                # Might be start of <think>, <tool_call>, etc
                                possible_tag = remaining[partial_open:].lower()
                                if possible_tag in [
                                    "<",
                                    "<t",
                                    "<th",
                                    "<thi",
                                    "<thin",
                                    "<think",
                                    "<to",
                                    "<too",
                                    "<tool",
                                    "<tool_",
                                    "<tool_c",
                                ]:
                                    incomplete_buffer = remaining[partial_open:]
                                    if partial_open > 0:
                                        code_part = remaining[:partial_open]
                                        full_response.append(code_part)
                                        yield self._sse({"chunk": code_part})
                                    break

                            # No tag, pure code
                            full_response.append(remaining)
                            yield self._sse({"chunk": remaining})
                            break

                # Check for file markers in recent output — also check thinking buffer
                # (some models output code entirely within think blocks)
                recent_code = "".join(full_response[-1000:])
                recent_thinking = "".join(thinking_response[-1000:])
                recent = recent_code if recent_code.strip() else recent_thinking
                file_matches = FILE_MARKER.findall(recent)
                for fname in file_matches:
                    fname_lower = fname.lower()
                    if fname_lower not in detected_files:
                        detected_files.add(fname_lower)
                        action = "Editing" if is_edit else "Creating"
                        progress_msg = f"{action} {fname_lower}..."
                        if progress_msg != last_progress:
                            last_progress = progress_msg
                            yield self._sse({"progress": progress_msg})

            # Finalize
            yield self._sse({"progress": "Processing files..."})

            final_text = "".join(full_response)
            final_text = re.sub(
                r"<(/?)(think|thought|tool_call|description)>",
                "",
                final_text,
                flags=re.IGNORECASE,
            )

            files = self.parse_multi_file_output(final_text)

            # ── FALLBACK: if model put all code inside <think> blocks ──────────
            # This happens with DeepSeek-based models and some OpenRouter models.
            # If no files were parsed from the outer response, try parsing the
            # thinking content — then re-emit those chunks as 'chunk' events so
            # the editor receives them correctly.
            if not files and thinking_response:
                thinking_text = "".join(thinking_response)
                thinking_text_clean = re.sub(
                    r"<(/?)(think|thought|tool_call|description)>",
                    "",
                    thinking_text,
                    flags=re.IGNORECASE,
                )
                files = self.parse_multi_file_output(thinking_text_clean)
                if files:
                    logger.info(
                        f"Fallback: parsed {len(files)} file(s) from thinking content."
                    )
                    # Re-emit code as chunk events so frontend editor shows the code
                    for f in files:
                        marker = f"--- {f['name']} ---"
                        yield self._sse({"chunk": f"\n{marker}\n{f['content']}\n"})
                    
                    # Emit files payload so views.py can capture last_files for Daytona
                    yield self._sse({"files": files})
                    
                    final_text = thinking_text_clean

            if not files:
                yield self._sse({"error": "No valid files generated"})
                return

            if is_edit and existing_files:
                merged = {f["name"].lower(): f["content"] for f in existing_files}
                for f in files:
                    merged[f["name"].lower()] = f["content"]
                files = [{"name": k, "content": v} for k, v in merged.items()]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) ready"})

            if not suppress_done:
                explanation = self.extract_description(raw_text=final_text)
                if explanation:
                    yield self._sse({"explanation": explanation})

                yield self._sse({"done": True, "files": files})

        except requests.exceptions.Timeout:
            logger.error("OpenRouter timeout")
            yield self._sse({"error": f"Timeout. {model_display} took too long."})

        except Exception as e:
            logger.error(f"OpenRouter error: {e}", exc_info=True)
            yield self._sse({"error": f"Generation failed: {str(e)}"})
