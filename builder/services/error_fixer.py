"""
AI service for generating code fixes for extracted errors.
Uses OpenRouter API with multiple fallback models to suggest fixes for identified errors.
"""
import os
import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ErrorFixer:
    """Generate code fixes using AI for identified errors."""

    # Fallback models if primary fails
    FALLBACK_MODELS = [
        "stepfun/step-3.5-flash:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "openai/gpt-oss-120b:free",
    ]

    GENERIC_FIX_TARGETS = {
        "file.js",
        "app.js",
        "main.js",
        "src/main.js",
        "src/main.ts",
        "src/main.tsx",
        "component.jsx",
        "src/components/component.jsx",
        "unknown",
    }

    AI_FIX_PROMPT = """You are an expert web developer helping fix code errors.

Given the error message and code context below, provide ONLY a valid JSON response with NO additional text, NO markdown, NO preamble:

{{"explanation": "Brief root cause", "fixed_code": "corrected code snippet", "files_to_update": ["{file_path}"], "alternative": "alternate fix if applicable"}}

Error: {error_message}
Language: {language}
File: {file_path}

Code Context:
{code_snippet}

RESPOND WITH ONLY THE JSON OBJECT:"""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER")
        self.api_base = "https://openrouter.ai/api/v1"
        self.primary_model = os.getenv("ERROR_FIXER_MODEL", "minimax/minimax-m2.5:free")
        self.current_model = self.primary_model

    def get_ai_fix(self, error_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate AI fix for an error using Claude via OpenRouter.

        Args:
            error_context: Dict with keys:
                - error_message: The error text
                - code_snippet: Optional code that caused error
                - file_path: Optional path to file with error
                - language: Optional programming language

        Returns:
            Dict with explanation, fixed_code, files_to_update, or None on error
        """
        error_message = error_context.get("error_message", "")
        code_snippet = error_context.get("code_snippet", "")[:1000]  # Truncate
        file_path = error_context.get("file_path", "unknown")
        language = error_context.get("language", "javascript")

        if not error_message:
            return None

        # 1. Try pattern-based fixes first for narrow, low-risk cases only.
        heuristic_fix = self._get_heuristic_fix(error_message, code_snippet, file_path)
        if heuristic_fix:
            logger.info(f"Using heuristic fix for: {error_message[:60]}")
            return heuristic_fix

        # 2. Try AI with fallback chain
        return self._call_ai_with_fallbacks(
            error_message, code_snippet, file_path, language
        )

    def _get_heuristic_fix(
        self, error_message: str, code_snippet: str, file_path: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Quick heuristic fixes for common errors without API cost.

        Args:
            error_message: The error text
            code_snippet: The code that caused error

        Returns:
            Fix dict or None if no pattern matches
        """
        error_lower = error_message.lower()
        # Avoid destructive placeholder rewrites for syntax/build failures.
        if any(
            token in error_lower
            for token in [
                "unexpected token",
                "syntaxerror",
                "parse error",
                "failed to resolve import",
                "does not provide an export",
                "internal server error",
            ]
        ):
            return None

        # Cannot read property of undefined
        if "cannot read property" in error_lower or "undefined" in error_lower:
            return None

        # Cannot read property of null
        if "cannot read" in error_lower and "null" in error_lower:
            return None

        # is not a function
        if "is not a function" in error_lower:
            return None

        # is not defined (ReferenceError)
        if "is not defined" in error_lower:
            return None

        # Unexpected token (SyntaxError)
        if "unexpected token" in error_lower:
            return None

        # Objects are not valid as React child
        if "react child" in error_lower or ("object" in error_lower and "not valid" in error_lower):
            return None

        # Module not found / import error
        if "module not found" in error_lower or "cannot find module" in error_lower:
            return None

        # Duplicate key in object
        if "duplicate" in error_lower and "key" in error_lower:
            return None

        # Whitespace issues
        if "unexpected indent" in error_lower or "indentation" in error_lower:
            return None

        return None

    def _call_ai_with_fallbacks(
        self, error_message: str, code_snippet: str, file_path: str, language: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call AI via OpenRouter with fallback to multiple models.

        Args:
            error_message: The error text
            code_snippet: Code that caused error
            file_path: Path to the file
            language: Programming language

        Returns:
            Dict with fix details or None on error
        """
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY not set")
            return None

        models_to_try = [self.primary_model] + self.FALLBACK_MODELS

        for model_idx, model in enumerate(models_to_try):
            try:
                logger.info(
                    f"Attempting AI fix with model {model_idx + 1}/{len(models_to_try)}: {model}"
                )
                fix_data = self._try_model(
                    error_message, code_snippet, file_path, language, model
                )
                if fix_data:
                    logger.info(f"Successfully got fix from model: {model}")
                    self.current_model = model
                    return fix_data
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Model {model} request failed: {str(e)[:100]}"
                )
                continue
            except Exception as e:
                logger.warning(
                    f"Model {model} failed: {str(e)[:100]}"
                )
                continue

        logger.error("All AI models failed for error fixing. Returning None.")
        return None

    def _try_model(
        self, error_message: str, code_snippet: str, file_path: str, language: str, model: str
    ) -> Optional[Dict[str, Any]]:
        """
        Try a single model for error fixing.

        Args:
            error_message: The error text
            code_snippet: Code that caused error
            file_path: Path to the file
            language: Programming language
            model: Model to use

        Returns:
            Dict with fix details or None on error
        """
        prompt = self.AI_FIX_PROMPT.format(
            error_message=error_message,
            code_snippet=code_snippet or "(No code context provided)",
            file_path=file_path,
            language=language,
        )

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://techspacehub.co.ke",
                    "X-Title": "TechSpaceHub",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                },
                timeout=(10, 20),
            )

            if response.status_code != 200:
                logger.warning(
                    f"OpenRouter API error: {response.status_code} (model={model})"
                )
                return None

            response_data = response.json()
            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            if not content or not content.strip():
                logger.warning(f"Empty response from {model}")
                return None

            fix_data = self._extract_json(content)
            if fix_data is None:
                logger.warning(
                    f"Could not extract JSON from {model}: {content[:200]}"
                )
                return None

            return self._normalize_fix_data(fix_data, file_path)

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout with model {model}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error with model {model}: {str(e)[:100]}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error with model {model}: {str(e)[:100]}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extract a JSON object from AI output that may contain
        markdown fences, thinking tags, or surrounding prose.
        """
        import re

        cleaned = text.strip()

        # 1. Try direct parse first (ideal case)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences:  ```json ... ```  or  ``` ... ```
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL
        )
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Strip <think>...</think> or <thought>...</thought> tags
        stripped = re.sub(
            r"<(think|thought)>.*?</\1>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
        )
        stripped = stripped.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 4. Find JSON object in text { ... }
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # 5. Last resort: try to extract JSON keys/values
        logger.error(f"Failed to extract JSON from: {cleaned[:300]}")
        return None

    def _preferred_fix_target(self, file_path: str) -> str:
        normalized = self._normalize_fix_target(file_path)
        return normalized or "src/app.jsx"

    def _normalize_fix_data(
        self, fix_data: Dict[str, Any], preferred_file_path: str
    ) -> Dict[str, Any]:
        normalized_fix = dict(fix_data or {})
        preferred_target = self._preferred_fix_target(preferred_file_path)
        raw_targets = normalized_fix.get("files_to_update") or []

        normalized_targets = []
        for target in raw_targets:
            normalized_target = self._normalize_fix_target(target)
            if not normalized_target or normalized_target in self.GENERIC_FIX_TARGETS:
                normalized_target = preferred_target
            if normalized_target not in normalized_targets:
                normalized_targets.append(normalized_target)

        if not normalized_targets:
            normalized_targets = [preferred_target]

        normalized_fix["files_to_update"] = normalized_targets
        return normalized_fix

    @staticmethod
    def _normalize_fix_target(path: str) -> str:
        candidate = (path or "").replace("\\", "/").strip().lower()
        if not candidate or candidate in {"unknown", "file.js"}:
            return ""
        return candidate


def get_error_fixer() -> ErrorFixer:
    """Factory function to get ErrorFixer instance."""
    return ErrorFixer()
