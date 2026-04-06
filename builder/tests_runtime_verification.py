import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from builder.models import GenerationSession

User = get_user_model()


class RuntimeVerificationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="verify-user",
            password="password123",
        )
        self.client.login(username="verify-user", password="password123")
        self.session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a startup landing page",
            output_type="react",
            files=[
                {"name": "src/App.jsx", "content": "export default function App(){return <main>Startup</main>}"},
                {"name": "src/main.js", "content": "const result = obj.property;"},
            ],
            status="done",
            build_status="completed",
            runtime_provider="webcontainer",
            runtime_status="ready",
            runtime_session_id="wc-789",
        )

    def test_runtime_verify_success_marks_session_verified(self):
        response = self.client.post(
            reverse("session-runtime-verify", args=[self.session.id]),
            data=json.dumps(
                {
                    "runtime_status": "ready",
                    "browser_errors": [],
                    "build_errors": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.verification_status, "verified")
        self.assertEqual(self.session.verification_attempts, 1)
        self.assertEqual(self.session.build_status, "completed")

    def test_runtime_verify_failure_marks_session_failed(self):
        response = self.client.post(
            reverse("session-runtime-verify", args=[self.session.id]),
            data=json.dumps(
                {
                    "runtime_status": "failed",
                    "error_message": "TypeError: Cannot read property 'map' of undefined at src/App.jsx:14:10",
                    "browser_errors": ["TypeError: Cannot read property 'map' of undefined"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.verification_status, "failed")
        self.assertEqual(self.session.build_status, "failed")
        self.assertIn("TypeError", self.session.last_error)

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_runtime_auto_fix_updates_session_and_tracks_attempts(self, mock_get_ai_fix):
        self.session.verification_status = "failed"
        self.session.last_error = "TypeError: Cannot read property 'map' of undefined"
        self.session.save()
        mock_get_ai_fix.return_value = {
            "explanation": "Use optional chaining on obj before property access.",
            "fixed_code": "const result = obj?.property ?? [];",
            "files_to_update": ["src/main.js"],
        }

        response = self.client.post(
            reverse("session-runtime-auto-fix", args=[self.session.id]),
            data=json.dumps(
                {
                    "error_message": "TypeError: Cannot read property 'map' of undefined",
                    "file_path": "src/main.js",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.auto_fix_attempts, 1)
        self.assertEqual(self.session.verification_status, "retrying")
        self.assertEqual(self.session.build_status, "generating")
        updated = next(file for file in self.session.files if file["name"] == "src/main.js")
        self.assertEqual(updated["content"], "const result = obj?.property ?? [];")
        self.assertEqual(response.json()["fix"]["files_to_update"], ["src/main.js"])

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_runtime_auto_fix_stops_after_max_attempts(self, mock_get_ai_fix):
        self.session.auto_fix_attempts = 2
        self.session.verification_status = "failed"
        self.session.save()

        response = self.client.post(
            reverse("session-runtime-auto-fix", args=[self.session.id]),
            data=json.dumps({"error_message": "TypeError: boom"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "AUTO_FIX_LIMIT_REACHED")
        mock_get_ai_fix.assert_not_called()
