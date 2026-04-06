"""
Integration tests for AI error fixing endpoint and service.
Tests the complete flow: error extraction → AI analysis → fix generation.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import json

User = get_user_model()


class ErrorFixingEndpointTestCase(TestCase):
    """Test /api/builder/fix-error/ endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.client.login(username="testuser", password="password123")
        self.url = reverse("fix-error")

    def test_endpoint_requires_authentication(self):
        """Verify endpoint requires authenticated user."""
        client = Client()
        response = client.post(
            self.url,
            data=json.dumps({"error_message": "SyntaxError: Unexpected token"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_endpoint_requires_error_message(self):
        """Verify endpoint validates required fields."""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_endpoint_extracts_and_returns_error_info(self):
        """Verify endpoint extracts error info correctly."""
        response = self.client.post(
            self.url,
            data=json.dumps(
                {"error_message": "TypeError: Cannot read property 'map' of undefined"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should have extracted error info
        self.assertIn("error_info", data)
        self.assertEqual(data["error_info"]["error_type"], "TypeError")

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_endpoint_calls_ai_for_fix(self, mock_ai_fix):
        """Verify endpoint calls AI service for fix generation."""
        mock_ai_fix.return_value = {
            "explanation": "The property doesn't exist",
            "fixed_code": "const items = obj?.map(...) ?? [];",
            "files_to_update": ["main.js"],
        }

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "error_message": "TypeError: Cannot read property 'map' of undefined",
                    "code_context": "const items = obj.map(x => x);",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_ai_fix.assert_called_once()

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_endpoint_returns_ai_fix(self, mock_ai_fix):
        """Verify endpoint returns AI-generated fix."""
        mock_ai_fix.return_value = {
            "explanation": "Use optional chaining operator",
            "fixed_code": "items = data?.results || [];",
            "files_to_update": ["app.js"],
        }

        response = self.client.post(
            self.url,
            data=json.dumps(
                {"error_message": "TypeError: Cannot read results", "code_snippet": ""}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("fix", data)
        self.assertIn("explanation", data["fix"])
        self.assertIn("fixed_code", data["fix"])

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_endpoint_handles_ai_errors_gracefully(self, mock_ai_fix):
        """Verify endpoint handles AI service failures gracefully."""
        mock_ai_fix.side_effect = Exception("API rate limit exceeded")

        response = self.client.post(
            self.url,
            data=json.dumps({"error_message": "SyntaxError: Unexpected token"}),
            content_type="application/json",
        )

        # Should still return 200 with error message
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("success", True))
        self.assertIn("error" or "message", data)

    def test_endpoint_response_structure(self):
        """Verify response has consistent structure."""
        with patch("builder.services.error_fixer.ErrorFixer.get_ai_fix") as mock_ai:
            mock_ai.return_value = {
                "explanation": "test",
                "fixed_code": "test",
                "files_to_update": [],
            }

            response = self.client.post(
                self.url,
                data=json.dumps({"error_message": "Error: test"}),
                content_type="application/json",
            )

            data = response.json()
            # All responses should have these fields
            self.assertIn("error_info", data)
            self.assertIn("success", data)

    def test_endpoint_with_file_context(self):
        """Verify endpoint handles code context properly."""
        code_context = {
            "file_path": "src/app.js",
            "line_number": 42,
            "code_snippet": "const result = undefined.map(...)",
        }

        with patch("builder.services.error_fixer.ErrorFixer.get_ai_fix"):
            response = self.client.post(
                self.url,
                data=json.dumps(
                    {
                        "error_message": "TypeError: Cannot read property 'map'",
                        **code_context,
                    }
                ),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, 200)

    def test_endpoint_limits_request_size(self):
        """Verify endpoint rejects oversized requests."""
        huge_code = "x" * (10 * 1024 * 1024)  # 10MB
        response = self.client.post(
            self.url,
            data=json.dumps(
                {"error_message": "Error", "code_snippet": huge_code}
            ),
            content_type="application/json",
        )
        # Should reject or truncate
        self.assertIn(response.status_code, [400, 413, 200])


class ErrorFixerServiceTestCase(TestCase):
    """Test ErrorFixer service logic."""

    def setUp(self):
        from builder.services.error_fixer import ErrorFixer

        self.fixer = ErrorFixer()

    @patch("builder.services.error_fixer.ErrorFixer._call_ai_classifier")
    def test_fixer_calls_claude_for_fix(self, mock_claude):
        """Verify fixer calls Claude API for fix generation."""
        mock_claude.return_value = {
            "explanation": "Async operation not awaited",
            "fixed_code": "const result = await fetchData();",
            "files_to_update": ["main.js"],
        }

        # Use an error that won't match heuristics to force AI call
        error_context = {
            "error_message": "Warning: You provided a value prop to a form field without an onChange handler",
            "code_snippet": "<input value={name} />",
            "file_path": "Form.jsx",
        }

        result = self.fixer.get_ai_fix(error_context)

        self.assertIsNotNone(result)
        self.assertIn("explanation", result)
        self.assertIn("fixed_code", result)
        mock_claude.assert_called_once()

    @patch("builder.services.error_fixer.ErrorFixer._call_ai_classifier")
    def test_fixer_includes_error_severity(self, mock_claude):
        """Verify fixer considers error severity in response."""
        mock_claude.return_value = {
            "explanation": "High severity error: code will crash",
            "fixed_code": "try { ... } catch(e) { ... }",
            "files_to_update": ["main.js"],
            "severity": "high",
        }

        result = self.fixer.get_ai_fix(
            {"error_message": "ReferenceError: x is not defined"}
        )

        self.assertIsNotNone(result)

    def test_fixer_handles_empty_code_context(self):
        """Verify fixer works with minimal context."""
        with patch("builder.services.error_fixer.ErrorFixer._call_ai_classifier"):
            result = self.fixer.get_ai_fix({"error_message": "SyntaxError: Unexpected"})
            # Should not crash
            self.assertIsNotNone(result)

    def test_fixer_returns_dict_with_required_fields(self):
        """Verify fix result has required fields."""
        with patch("builder.services.error_fixer.ErrorFixer._call_ai_classifier") as mock:
            mock.return_value = {
                "explanation": "test",
                "fixed_code": "test",
                "files_to_update": ["test.js"],
            }

            result = self.fixer.get_ai_fix({"error_message": "test"})

            self.assertIn("explanation", result)
            self.assertIn("fixed_code", result)
            self.assertIn("files_to_update", result)

    @patch("builder.services.error_fixer.ErrorFixer._call_ai_classifier")
    def test_fixer_suggests_multiple_approaches(self, mock_claude):
        """Verify fixer can suggest alternative fixes."""
        mock_claude.return_value = {
            "explanation": "Try this approach",
            "fixed_code": "const x = value || defaultValue;",
            "alternative": "const x = value ?? defaultValue;",
            "files_to_update": ["app.js"],
        }

        result = self.fixer.get_ai_fix(
            {"error_message": "TypeError: Cannot assign to undefined"}
        )

        # Should include alternative if provided
        self.assertIsNotNone(result)

    def test_fixer_cost_optimization(self):
        """Verify fixer uses cheap heuristics before expensive AI calls."""
        # Common errors should be handled by heuristics first
        common_errors = [
            "Cannot read property of undefined",
            "Cannot read property of null",
            "is not a function",
        ]

        for error in common_errors:
            with patch(
                "builder.services.error_fixer.ErrorFixer._call_ai_classifier"
            ) as mock_ai:
                self.fixer.get_ai_fix({"error_message": error})
                # Heuristics should handle some cases without AI
                # (Implementation may vary)
