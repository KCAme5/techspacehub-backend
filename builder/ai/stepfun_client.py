# builder/ai/openrouter_client.py
import os, json, logging
import requests
from .base import BaseWebsiteGenerator

class OpenRouterBuilderClient(BaseWebsiteGenerator):
    def __init__(self, model="stepfun/step-3.5-flash:free"):
        self.api_key = os.environ.get("OPEN_ROUTER")
        self.model   = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def _sse(self, payload):
        return f"data: {json.dumps(payload)}\n\n"

    def stream_generation(self, prompt, existing_files=None, output_type='react'):
        if not self.api_key:
            yield self._sse({"error": "OPENROUTER_API_KEY missing"})
            return

        is_edit = bool(existing_files)
        system  = self._build_edit_system_prompt() if is_edit else self._build_system_prompt(output_type)
        user    = self._build_user_message(prompt, existing_files, output_type, is_edit)

        yield self._sse({"progress": "Connecting to Step 3.5 Flash..."})

        full_response = ""
        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://techspacehub.com",  # shows on OpenRouter leaderboard
                    "X-Title":       "TechSpaceHub Build by AI",
                },
                json={
                    "model":      self.model,
                    "messages":   [{"role":"system","content":system},
                                   {"role":"user",  "content":user}],
                    "max_tokens": 16000,
                    "stream":     True,
                    "temperature": 0.3,
                },
                stream=True,
                timeout=120,
            )

            yield self._sse({"progress": "Building structure..."})

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        token = json.loads(chunk)["choices"][0]["delta"].get("content","")
                        if token:
                            full_response += token
                            yield self._sse({"chunk": token})
                    except Exception:
                        pass

            files = self.parse_multi_file_output(full_response)
            if not files:
                files = [{"name": "index.html", "content": full_response}]

            if is_edit and existing_files:
                merged = {f["name"]: f["content"] for f in existing_files}
                for f in files:
                    merged[f["name"]] = f["content"]
                files = [{"name":k,"content":v} for k,v in merged.items()]

            yield self._sse({"progress": f"Complete — {len(files)} file(s) generated"})
            yield self._sse({"done": True, "files": files})

        except Exception as e:
            logging.error(f"OpenRouter error: {e}")
            yield self._sse({"error": str(e)})