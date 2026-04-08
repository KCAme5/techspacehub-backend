"""
AI service for generating code fixes for extracted errors.
Uses OpenRouter API with Claude to suggest fixes for identified errors.
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
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4-turbo",
        "google/gemini-2.0-flash-001",
    ]

    AI_FIX_PROMPT = """You are an expert web developer helping fix code errors.

Given the error message and code context below, provide ONLY a valid JSON response with NO additional text, NO markdown, NO preamble:

{{"explanation": "Brief root cause", "fixed_code": "corrected code snippet", "files_to_update": ["file.js"], "alternative": "alternate fix if applicable"}}

Error: {error_message}
Language: {language}
File: {file_path}

Code Context:
{code_snippet}

RESPOND WITH ONLY THE JSON OBJECT:"""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1"
        self.primary_model = os.getenv("ERROR_FIXER_MODEL", "stepfun/step-3.5-flash:free")
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

        # 1. Try pattern-based fixes first (free, instant)
        heuristic_fix = self._get_heuristic_fix(error_message, code_snippet)
        if heuristic_fix:
            logger.info(f"Using heuristic fix for: {error_message[:60]}")
            return heuristic_fix

        # 2. Try AI with fallback chain
        return self._call_ai_with_fallbacks(
            error_message, code_snippet, file_path, language
        )

    def _get_heuristic_fix(
        self, error_message: str, code_snippet: str
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

        # Cannot read property of undefined
        if "cannot read property" in error_lower or "undefined" in error_lower:
            return {
                "explanation": "The object is undefined. Use optional chaining to safely access properties.",
                "fixed_code": "// Use optional chaining:\nconst result = obj?.property ?? defaultValue;",
                "files_to_update": ["src/main.js"],
            }

        # Cannot read property of null
        if "cannot read" in error_lower and "null" in error_lower:
            return {
                "explanation": "The object is null. Check if it exists before accessing.",
                "fixed_code": "// Add null check:\nif (obj !== null && obj !== undefined) {\n  obj.method();\n}",
                "files_to_update": ["src/main.js"],
            }

        # is not a function
        if "is not a function" in error_lower:
            return {
                "explanation": "The variable is not a function. Ensure it's defined as a function.",
                "fixed_code": "// Ensure it's a function:\nif (typeof myFunc === 'function') {\n  myFunc();\n}",
                "files_to_update": ["src/main.js"],
            }

        # is not defined (ReferenceError)
        if "is not defined" in error_lower:
            return {
                "explanation": "Variable is used before declaration or has a typo. Check variable names.",
                "fixed_code": "// Declare the variable:\nlet myVariable = value;  // or const myVariable = value;",
                "files_to_update": ["src/main.js"],
            }

        # Unexpected token (SyntaxError)
        if "unexpected token" in error_lower:
            return {
                "explanation": "Syntax error - likely missing brace, parenthesis, or semicolon.",
                "fixed_code": "// Check for missing: }\n// Check for missing: )\n// Check for missing: ;",
                "files_to_update": ["src/main.js"],
            }

        # Objects are not valid as React child
        if "react child" in error_lower or ("object" in error_lower and "not valid" in error_lower):
            return {
                "explanation": "Can't render objects or promises directly in JSX. Extract the data you need.",
                "fixed_code": "// Don't: <div>{object}</div>\n// Do: <div>{object.property}</div>",
                "files_to_update": ["src/components/Component.jsx"],
            }

        # Module not found / import error
        if "module not found" in error_lower or "cannot find module" in error_lower:
            return {
                "explanation": "Module/dependency is not installed or import path is incorrect.",
                "fixed_code": "// Check:\n// 1. npm install the package\n// 2. Verify import path matches exported name",
                "files_to_update": ["package.json"],
            }

        # Duplicate key in object
        if "duplicate" in error_lower and "key" in error_lower:
            return {
                "explanation": "Object has duplicate property keys. Remove the duplicate.",
                "fixed_code": "// Remove duplicate key:\nconst obj = {\n  name: 'value',\n  // name: 'duplicate'  <- REMOVE THIS\n};",
                "files_to_update": ["src/main.js"],
            }

        # Whitespace issues
        if "unexpected indent" in error_lower or "indentation" in error_lower:
            return {
                "explanation": "Indentation error. Use consistent spacing (2 or 4 spaces, not tabs).",
                "fixed_code": "// Fix indentation:\nif (true) {\n  // 2 space indent\n  doSomething();\n}",
                "files_to_update": ["src/main.js"],
            }

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
                timeout=30,
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

            return fix_data

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


def get_error_fixer() -> ErrorFixer:
    """Factory function to get ErrorFixer instance."""
    return ErrorFixer()

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

        # Check for pattern-based fixes first (cheap heuristics)
        heuristic_fix = self._get_heuristic_fix(error_message, code_snippet)
        if heuristic_fix:
            return heuristic_fix

        # Fall back to Claude for complex errors
        return self._call_ai_classifier(
            error_message, code_snippet, file_path, language
        )

    def _get_heuristic_fix(
        self, error_message: str, code_snippet: str
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

        # Cannot read property of undefined
        if "cannot read property" in error_lower:
            return {
                "explanation": "The object is undefined. Use optional chaining to safely access properties.",
                "fixed_code": "// Use optional chaining:\nconst result = obj?.property ?? defaultValue;",
                "files_to_update": ["src/main.js"],
            }

        # Cannot read property of null
        if "cannot read property" in error_lower and "null" in error_lower:
            return {
                "explanation": "The object is null. Check if it exists before accessing.",
                "fixed_code": "// Add null check:\nif (obj !== null && obj !== undefined) {\n  obj.method();\n}",
                "files_to_update": ["src/main.js"],
            }

        # is not a function
        if "is not a function" in error_lower:
            return {
                "explanation": "The variable is not a function. Verify it's the right variable and it's defined as a function.",
                "fixed_code": "// Ensure it's a function:\nif (typeof myFunc === 'function') {\n  myFunc();\n}",
                "files_to_update": ["src/main.js"],
            }

        # is not defined (ReferenceError)
        if "is not defined" in error_lower:
            return {
                "explanation": "Variable is used before declaration or has a typo. Check variable names.",
                "fixed_code": "// Declare the variable:\nlet myVariable = value;  // or const myVariable = value;",
                "files_to_update": ["src/main.js"],
            }

        # Unexpected token (SyntaxError)
        if "unexpected token" in error_lower:
            return {
                "explanation": "Syntax error - likely missing brace, parenthesis, or semicolon.",
                "fixed_code": "// Common fixes:\n// Missing closing brace: }\n// Missing closing paren: )\n// Missing semicolon: ;",
                "files_to_update": ["src/main.js"],
            }

        # Objects are not valid as React child
        if "react child" in error_lower or "object" in error_lower:
            return {
                "explanation": "Can't render objects or promises directly in JSX. Extract the data you need.",
                "fixed_code": "// Don't:\n<div>{object}</div>\n// Do:\n<div>{object.property}</div>",
                "files_to_update": ["src/components/Component.jsx"],
            }

        return None

    def _call_ai_classifier(
        self, error_message: str, code_snippet: str, file_path: str, language: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call AI via OpenRouter for fix generation.

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
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                },
                timeout=45,
            )

            if response.status_code != 200:
                logger.error(
                    "OpenRouter API error: %s — %s (model=%s)",
                    response.status_code,
                    response.text[:500],
                    self.model,
                )
                return None

            response_data = response.json()
            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            if not content or not content.strip():
                logger.error("AI returned empty content (model=%s)", self.model)
                return None

            fix_data = self._extract_json(content)
            if fix_data is None:
                logger.error(
                    "Could not extract JSON from AI response (model=%s): %.300s",
                    self.model,
                    content,
                )
            return fix_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in AI fix: {str(e)}", exc_info=True)
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

        # 4. Find the first { ... } block in the remaining text
        brace_match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None


# Singleton instance
_fixer_instance = None


def get_error_fixer() -> ErrorFixer:
    """Get or create singleton ErrorFixer instance."""
    global _fixer_instance
    if _fixer_instance is None:
        _fixer_instance = ErrorFixer()
    return _fixer_instance
