"""
Unit tests for error extraction service.
Tests error parsing, categorization, and formatting.
"""
from django.test import TestCase
from builder.services.error_extractor import ErrorExtractor, ErrorInfo


class ErrorExtractionTestCase(TestCase):
    """Test errorExtractor service for parsing console errors."""

    def setUp(self):
        self.extractor = ErrorExtractor()

    def test_extract_javascript_syntax_error(self):
        """Parse JavaScript syntax errors correctly."""
        error_msg = "Uncaught SyntaxError: Unexpected token } at line 15, column 5"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "SyntaxError")
        self.assertIn("Unexpected token", result.message)
        self.assertEqual(result.language, "javascript")

    def test_extract_javascript_runtime_error(self):
        """Parse JavaScript runtime errors correctly."""
        error_msg = "TypeError: Cannot read property 'map' of undefined at fetchData (app.js:42:15)"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "TypeError")
        self.assertIn("Cannot read property", result.message)
        self.assertEqual(result.language, "javascript")

    def test_extract_css_error(self):
        """Parse CSS parsing errors correctly."""
        error_msg = "CSS Parse Error: Invalid property value at line 23"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "CSSError")
        self.assertEqual(result.language, "css")

    def test_extract_html_error(self):
        """Parse HTML validation errors correctly."""
        error_msg = "HTML Error: Unclosed tag <div> at line 10"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "HTMLError")
        self.assertEqual(result.language, "html")

    def test_extract_react_error(self):
        """Parse React-specific errors correctly."""
        error_msg = "Error: Objects are not valid as a React child. Found: [object Promise]"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "ReactError")
        self.assertIn("React child", result.message)
        # React errors should be identified as 'react' language specifically
        self.assertIn(result.language, ["react", "javascript"])

    def test_extract_with_context(self):
        """Extract errors with additional context information."""
        error_msg = "TypeError: Cannot read property 'length' of undefined\nStack trace:\n    at processArray (main.js:15:20)\n    at handleClick (app.js:42:10)"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.error_type, "TypeError")
        # Context should include stack trace info if available
        self.assertIsNotNone(result.context)

    def test_invalid_error_format(self):
        """Handle invalid/unrecognizable error formats gracefully."""
        error_msg = "Some random string that is not an error"
        result = self.extractor.extract(error_msg)

        # Should still return error info but mark as low confidence
        self.assertEqual(result.error_type, "UnknownError")
        self.assertFalse(result.is_obvious_error)

    def test_warning_vs_error(self):
        """Distinguish between warnings and errors."""
        warning = "Warning: Deprecated API used at line 5"
        alert = "Alert: This feature is experimental"

        warning_result = self.extractor.extract(warning)
        alert_result = self.extractor.extract(alert)

        # Warnings should be marked differently
        self.assertFalse(warning_result.is_blocking)
        self.assertFalse(alert_result.is_blocking)

    def test_empty_error_message(self):
        """Handle empty error messages gracefully."""
        result = self.extractor.extract("")
        self.assertFalse(result.is_valid)

    def test_error_suggestion_provided(self):
        """Verify suggestions are provided for common errors."""
        common_errors = [
            "undefined is not a function",
            "Cannot read property",
            "Unexpected token",
        ]

        for error in common_errors:
            result = self.extractor.extract(error)
            self.assertIsNotNone(result.suggestion)
            self.assertTrue(len(result.suggestion) > 0)

    def test_multiple_errors_concatenation(self):
        """Extract from concatenated error messages."""
        multi_error = (
            "Error 1: TypeError: Cannot read property\n"
            "Error 2: ReferenceError: x is not defined"
        )
        result = self.extractor.extract(multi_error)

        # Should extract primary error
        self.assertTrue(result.is_valid)
        self.assertIn("TypeError", result.error_type)

    def test_error_with_file_path(self):
        """Extract file path from error message."""
        error_msg = "SyntaxError: Unexpected token at /src/components/Button.jsx:25:10"
        result = self.extractor.extract(error_msg)

        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.file_path)
        self.assertIn("Button.", result.file_path or "")

    def test_extract_vite_unexpected_token_overlay_error(self):
        error_msg = "[plugin:vite:react-babel] /home/demo/src/App.jsx: Unexpected token (106:1)"
        result = self.extractor.extract(error_msg)

        self.assertEqual(result.error_type, "SyntaxError")
        self.assertTrue(result.is_blocking)
        self.assertEqual(result.file_path, "/home/demo/src/App.jsx")

    def test_error_info_has_all_required_fields(self):
        """Verify ErrorInfo object has all necessary fields."""
        error_msg = "TypeError: Property 'x' is undefined"
        result = self.extractor.extract(error_msg)

        # Check required fields exist
        self.assertTrue(hasattr(result, "is_valid"))
        self.assertTrue(hasattr(result, "error_type"))
        self.assertTrue(hasattr(result, "message"))
        self.assertTrue(hasattr(result, "language"))
        self.assertTrue(hasattr(result, "severity"))
        self.assertTrue(hasattr(result, "suggestion"))
        self.assertTrue(hasattr(result, "context"))
        self.assertTrue(hasattr(result, "file_path"))
        self.assertTrue(hasattr(result, "line_number"))
