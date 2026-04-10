import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from builder.models import GenerationSession
from builder.services.runtime_provider import WebContainerRuntimeProvider, get_runtime_provider

User = get_user_model()


class RuntimeProviderTestCase(TestCase):
    def test_react_projects_use_webcontainer_provider(self):
        provider = get_runtime_provider("react")

        self.assertIsInstance(provider, WebContainerRuntimeProvider)

    def test_webcontainer_payload_contains_runtime_commands(self):
        user = User.objects.create_user(username="provider-user", password="password123")
        session = GenerationSession.objects.create(
            user=user,
            prompt="Build a fintech landing page",
            output_type="react",
            files=[{"name": "src/App.jsx", "content": "export default function App(){return <div /> }"}],
            status="done",
            build_status="completed",
        )

        bundle = WebContainerRuntimeProvider().prepare(session)

        self.assertEqual(bundle.provider, "webcontainer")
        self.assertEqual(bundle.runtime_status, "prepared")
        install_command = bundle.payload["commands"]["install"]
        self.assertEqual(install_command[0:2], ["npm", "install"])
        self.assertIn("--no-fund", install_command)
        self.assertIn("--no-audit", install_command)
        self.assertIn("--progress=false", install_command)
        self.assertIn("--cache", install_command)
        self.assertIn("/tmp/.npm", install_command)
        self.assertIn("--package-lock=false", install_command)
        self.assertEqual(bundle.payload["preview"]["port"], 4173)


class RuntimeEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="runtime-user",
            password="password123",
        )
        self.client.login(username="runtime-user", password="password123")
        self.session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a restaurant landing page",
            output_type="react",
            files=[
                {"name": "src/App.jsx", "content": "export default function App(){return <main>Restaurant</main>}"},
                {"name": "package.json", "content": "{\"name\":\"demo\"}"},
            ],
            status="done",
            build_status="completed",
            intent_type="build_new",
        )

    def test_prepare_runtime_returns_webcontainer_bootstrap_payload(self):
        response = self.client.post(reverse("session-runtime-prepare", args=[self.session.id]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.session.refresh_from_db()
        self.assertEqual(data["runtime_provider"], "webcontainer")
        self.assertEqual(self.session.runtime_provider, "webcontainer")
        self.assertEqual(self.session.runtime_status, "prepared")
        self.assertTrue(self.session.runtime_session_id)
        self.assertEqual(data["runtime"]["commands"]["dev"][0:3], ["npm", "run", "dev"])

    def test_runtime_event_persists_preview_url_and_metadata(self):
        self.session.runtime_provider = "webcontainer"
        self.session.runtime_status = "prepared"
        self.session.runtime_session_id = "wc-123"
        self.session.save()

        response = self.client.post(
            reverse("session-runtime-event", args=[self.session.id]),
            data=json.dumps(
                {
                    "runtime_status": "ready",
                    "runtime_session_id": "wc-123",
                    "preview_url": "https://local.webcontainer/preview",
                    "runtime_metadata": {"dev_server_port": 4173},
                    "log": "Server ready on port 4173",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.runtime_status, "ready")
        self.assertEqual(self.session.preview_url, "https://local.webcontainer/preview")
        self.assertEqual(self.session.runtime_metadata["dev_server_port"], 4173)
        self.assertTrue(any("Server ready on port 4173" in entry for entry in self.session.build_logs))

    def test_runtime_detail_endpoint_exposes_runtime_state(self):
        self.session.runtime_provider = "webcontainer"
        self.session.runtime_status = "running"
        self.session.runtime_session_id = "wc-456"
        self.session.runtime_metadata = {"install_state": "complete"}
        self.session.preview_url = "https://preview.local/demo"
        self.session.save()

        response = self.client.get(reverse("session-runtime-detail", args=[self.session.id]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["runtime_provider"], "webcontainer")
        self.assertEqual(data["runtime_status"], "running")
        self.assertEqual(data["runtime_session_id"], "wc-456")
        self.assertEqual(data["preview_url"], "https://preview.local/demo")
