import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from builder.models import GenerationSession
from builder.services.credit_service import get_or_create_credits

User = get_user_model()


class SessionLifecycleTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="lifecycle-user",
            password="password123",
        )
        self.client.login(username="lifecycle-user", password="password123")

    def _consume_stream(self, response):
        self.assertTrue(response.streaming)
        return "".join(
            chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )

    @patch("builder.services.agent_orchestrator.AgentOrchestrator.stream_build")
    def test_generate_persists_completed_session_state(self, mock_stream_build):
        mock_stream_build.return_value = iter(
            [
                'data: {"status":"Initializing agent orchestrator..."}\n\n',
                'data: {"progress":"Connected"}\n\n',
                'data: {"complete": true, "files": [{"name":"src/App.jsx","content":"export default function App(){return <div>Done</div>}"}], "summary":"Build complete", "explanation":"Created the requested site.", "preview_url":"https://preview.local/session"}\n\n',
            ]
        )

        response = self.client.post(
            reverse("generate"),
            data=json.dumps(
                {
                    "prompt": "Build a landing page for a gym",
                    "output_type": "react",
                    "model": "trinity",
                }
            ),
            content_type="application/json",
        )
        body = self._consume_stream(response)

        session = GenerationSession.objects.get(user=self.user)
        self.assertIn('"complete": true', body.lower())
        self.assertEqual(session.status, "done")
        self.assertEqual(session.build_status, "completed")
        self.assertEqual(session.intent_type, "build_new")
        self.assertEqual(session.build_attempts, 1)
        self.assertEqual(session.preview_url, "https://preview.local/session")
        self.assertEqual(session.last_error, "")
        self.assertEqual(len(session.files), 1)
        self.assertIn("Created the requested site.", session.explanation)
        self.assertTrue(any("Connected" in entry for entry in session.build_logs))

    @patch("builder.services.agent_orchestrator.AgentOrchestrator.stream_build")
    def test_generate_failure_marks_session_and_restores_credit(self, mock_stream_build):
        mock_stream_build.return_value = iter(
            [
                'data: {"status":"Initializing agent orchestrator..."}\n\n',
                'data: {"error":"Build failed because src/App.jsx is invalid."}\n\n',
            ]
        )
        credits, _ = get_or_create_credits(self.user)
        before = credits.credits

        response = self.client.post(
            reverse("generate"),
            data=json.dumps(
                {
                    "prompt": "Build a SaaS landing page",
                    "output_type": "react",
                    "model": "trinity",
                }
            ),
            content_type="application/json",
        )
        self._consume_stream(response)

        credits.refresh_from_db()
        session = GenerationSession.objects.get(user=self.user)
        self.assertEqual(session.status, "error")
        self.assertEqual(session.build_status, "failed")
        self.assertEqual(session.last_error, "Build failed because src/App.jsx is invalid.")
        self.assertEqual(credits.credits, before)

    @patch("builder.services.agent_orchestrator.AgentOrchestrator.stream_build")
    def test_chat_edit_persists_lifecycle_fields(self, mock_stream_build):
        session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a portfolio site",
            output_type="react",
            files=[{"name": "src/App.jsx", "content": "export default function App(){return <div>Old</div>}"}],
            status="done",
            build_status="completed",
            intent_type="build_new",
        )
        mock_stream_build.return_value = iter(
            [
                'data: {"status":"Applying edit"}\n\n',
                'data: {"complete": true, "files": [{"name":"src/App.jsx","content":"export default function App(){return <div>New</div>}"}], "explanation":"Updated the hero section.", "preview_url":"https://preview.local/updated"}\n\n',
            ]
        )

        response = self.client.post(
            reverse("session-chat", args=[session.id]),
            data=json.dumps({"message": "Make the hero section more modern"}),
            content_type="application/json",
        )
        self._consume_stream(response)

        session.refresh_from_db()
        self.assertEqual(session.status, "done")
        self.assertEqual(session.build_status, "completed")
        self.assertEqual(session.intent_type, "edit_existing")
        self.assertEqual(session.build_attempts, 1)
        self.assertEqual(session.preview_url, "https://preview.local/updated")
        self.assertIn("Updated the hero section.", session.explanation)

    def test_session_serializer_exposes_lifecycle_fields(self):
        session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a law firm website",
            output_type="react",
            status="done",
            intent_type="build_new",
            build_status="completed",
            build_attempts=2,
            preview_url="https://preview.local/law",
            last_error="",
            build_logs=["Initializing", "Build completed"],
        )

        response = self.client.get(reverse("session-detail", args=[session.id]))
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["intent_type"], "build_new")
        self.assertEqual(data["build_status"], "completed")
        self.assertEqual(data["build_attempts"], 2)
        self.assertEqual(data["preview_url"], "https://preview.local/law")
        self.assertEqual(data["build_logs"], ["Initializing", "Build completed"])
