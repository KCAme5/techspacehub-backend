"""
Error extraction service for parsing console errors from web applications.
Identifies error type, language, severity, and provides helpful suggestions.
"""
import re
import json
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ErrorInfo:
    """Structured information about an extracted error."""

    is_valid: bool = False
    error_type: str = "UnknownError"
    message: str = ""
    language: str = "javascript"  # javascript, css, html, python, etc.
    severity: str = "warning"  # error, warning, info
    suggestion: Optional[str] = None
    context: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    is_blocking: bool = True  # Does this prevent execution?
    is_obvious_error: bool = True  # Can be fixed with obvious solution?


class ErrorExtractor:
    """Extract and categorize errors from console messages."""

    # Error patterns for different error types
    ERROR_PATTERNS = {
        "CSSError": re.compile(
            r"(?:CSS|Style)\s*(?:Parse\s*)?Error:?\s*(.+?)(?:\s+at|$)",
            re.IGNORECASE,
        ),
        "SyntaxError": re.compile(
            r"(?:(?:Syntax|Parse)\s*Error:?|Unexpected token|Unterminated regular expression|Unexpected end of input)\s*(.+?)(?:\s+at|$)",
            re.IGNORECASE,
        ),
        "TypeError": re.compile(
            r"TypeError:?\s*(.+?)(?:\s+at|$)", re.IGNORECASE
        ),
        "ReferenceError": re.compile(
            r"ReferenceError:?\s*(.+?)(?:\s+at|$)", re.IGNORECASE
        ),
        "RangeError": re.compile(
            r"RangeError:?\s*(.+?)(?:\s+at|$)", re.IGNORECASE
        ),
        "ReactError": re.compile(
            r"(?:React|Objects are not valid as a React child)", re.IGNORECASE
        ),
        "HTMLError": re.compile(
            r"HTML\s*Error:?\s*(.+?)(?:\s+at|$)", re.IGNORECASE
        ),
        "NetworkError": re.compile(
            r"(?:Network|Fetch|CORS)\s*Error:?\s*(.+?)(?:\s+at|$)", re.IGNORECASE
        ),
    }

    # Language detection patterns
    LANGUAGE_PATTERNS = {
        "javascript": re.compile(
            r"(?:\.js|\.jsx|\.ts|\.tsx|TypeError|ReferenceError|is not a function|Cannot read property)",
            re.IGNORECASE,
        ),
        "css": re.compile(
            r"(?:\.css|CSS|Style|property value|selector)", re.IGNORECASE
        ),
        "html": re.compile(r"(?:\.html|HTML|tag|element)", re.IGNORECASE),
        "react": re.compile(
            r"(?:React|JSX|component|hook|render)", re.IGNORECASE
        ),
    }

    # Common error suggestions
    COMMON_FIXES = {
        "Cannot read property": "Check if object exists before accessing property (e.g., use optional chaining: obj?.prop)",
        "is not a function": "Verify the variable is actually a function before calling it",
        "Unexpected token": "Check syntax at the indicated line - look for missing braces, parentheses, or semicolons",
        "is not defined": "Ensure variable is declared before use - check for typos in variable name",
        "Cannot read property 'map'": "Use optional chaining or null coalescing: array?.map(...) || []",
        "Objects are not valid as a React child": "Don't pass objects/promises directly to JSX - render their properties or use a key",
        "Unclosed tag": "Verify all HTML tags are properly closed with closing tags",
        "Invalid property value": "Check CSS syntax - ensure values match expected format",
    }

    def extract(self, error_message: str) -> ErrorInfo:
        """
        Extract structured error information from error message.

        Args:
            error_message: Raw error message from console

        Returns:
            ErrorInfo object with parsed error details
        """
        if not error_message or not error_message.strip():
            return ErrorInfo(is_valid=False)

        error_info = ErrorInfo()

        # Split into lines and focus on first line for error type detection
        lines = error_message.split("\n")
        first_line = lines[0]

        # Detect error type from first line
        for error_type, pattern in self.ERROR_PATTERNS.items():
            if pattern.search(first_line):
                error_info.error_type = error_type
                error_info.is_valid = True
                match = pattern.search(first_line)
                if match.groups():
                    error_info.message = match.group(1).strip()
                else:
                    error_info.message = first_line[:200]
                break

        # If no specific error type found, check if it's any other error
        if not error_info.is_valid:
            if any(
                keyword in first_line.lower()
                for keyword in ["error", "exception", "failed", "unexpected token", "does not provide an export"]
            ):
                error_info.error_type = "UnknownError"
                error_info.message = first_line[:200]
                error_info.is_obvious_error = False
            else:
                # Might be a warning or other non-blocking message
                error_info.error_type = "UnknownError"
                error_info.is_blocking = False
                error_info.severity = "warning"

        # Detect language
        for lang, pattern in self.LANGUAGE_PATTERNS.items():
            if pattern.search(error_message):
                error_info.language = lang
                break

        # Override language to react for React errors
        if error_info.error_type == "ReactError" and error_info.language != "react":
            error_info.language = "react"

        # Extract file path if present
        file_match = re.search(
            r"((?:/|[a-zA-Z]:\\|[.\w-]+/)[^:\s]+\.(?:js|jsx|tsx?|css|html|json))",
            error_message,
            re.IGNORECASE,
        )
        if not file_match:
            file_match = re.search(
                r"at\s+([^(\s]+\.(?:js|jsx|tsx?|css|html|json))",
                error_message,
                re.IGNORECASE,
            )
        if file_match:
            error_info.file_path = file_match.group(1)

        # Extract line number if present
        line_match = re.search(r"(?:line|:)?\s*(\d+)(?::(\d+))?", error_message)
        if line_match:
            error_info.line_number = int(line_match.group(1))

        # Set severity based on error type
        error_info.severity = "error" if error_info.is_blocking else "warning"

        # Extract context (multi-line errors, stack traces)
        if len(lines) > 1:
            # Include next 4 lines of context
            error_info.context = "\n".join(lines[1:5])

        # Suggest common fixes
        for error_key, suggestion in self.COMMON_FIXES.items():
            if error_key.lower() in error_message.lower():
                error_info.suggestion = suggestion
                break

        # Fallback suggestion
        if not error_info.suggestion:
            error_info.suggestion = f"Check the {error_info.error_type} - review the syntax and ensure all variables are defined"

        return error_info


# Singleton instance
_extractor_instance = None


def get_error_extractor() -> ErrorExtractor:
    """Get or create singleton ErrorExtractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ErrorExtractor()
    return _extractor_instance
