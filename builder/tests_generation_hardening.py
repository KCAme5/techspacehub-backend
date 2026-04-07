import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from builder.ai.base import BaseWebsiteGenerator
from builder.models import GenerationSession

User = get_user_model()


class GenerationHardeningTestCase(TestCase):
    def setUp(self):
        self.generator = BaseWebsiteGenerator()

    def test_react_scaffolding_enforces_supported_dependencies_and_files(self):
        files = [
            {
                "name": "package.json",
                "content": json.dumps(
                    {
                        "name": "demo",
                        "dependencies": {
                            "react": "^18.2.0",
                            "left-pad": "^1.3.0",
                        },
                        "devDependencies": {
                            "vite": "^4.0.0",
                        },
                    }
                ),
            }
        ]

        result = self.generator.ensure_essential_files(files, output_type="react")
        file_map = {file_data["name"]: file_data["content"] for file_data in result}
        package_json = json.loads(file_map["package.json"])

        self.assertIn("src/main.jsx", file_map)
        self.assertIn("src/App.jsx", file_map)
        self.assertIn("src/index.css", file_map)
        self.assertIn("tailwind.config.js", file_map)
        self.assertIn("postcss.config.js", file_map)
        self.assertNotIn("left-pad", package_json["dependencies"])
        self.assertEqual(package_json["scripts"]["build"], "vite build")
        self.assertIn("@vitejs/plugin-react", package_json["devDependencies"])
        self.assertIn("Cross-Origin-Opener-Policy", file_map["vite.config.js"])

    def test_react_main_entry_is_normalized_to_jsx(self):
        files = [
            {"name": "src/main.js", "content": "console.log('wrong entry')"},
            {"name": "src/App.js", "content": "export default function App(){return null}"},
        ]

        result = self.generator.ensure_essential_files(files, output_type="react")
        file_names = {file_data["name"] for file_data in result}

        self.assertIn("src/main.jsx", file_names)
        self.assertIn("src/App.jsx", file_names)
        self.assertNotIn("src/main.js", file_names)
        self.assertNotIn("src/App.js", file_names)

    def test_invalid_public_svg_summary_is_dropped(self):
        files = [
            {
                "name": "public/vite.svg",
                "content": "Complete production-ready portfolio React app built with Vite.",
            },
            {
                "name": "src/App.jsx",
                "content": "export default function App(){return <main>Hello</main>}",
            },
        ]

        result = self.generator.ensure_essential_files(files, output_type="react")
        file_names = {file_data["name"] for file_data in result}

        self.assertNotIn("public/vite.svg", file_names)
        self.assertIn("src/App.jsx", file_names)

    def test_extract_description_falls_back_to_plain_summary(self):
        summary = (
            "Complete production-ready portfolio React app built with Vite, Tailwind CSS, "
            "Framer Motion, and Lucide React.\n\n- Responsive navigation\n- Animated hero"
        )

        extracted = self.generator.extract_description(summary)
        self.assertIn("portfolio React app", extracted)


class AutoFixGuardrailTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="guard-user",
            password="password123",
        )
        self.client.login(username="guard-user", password="password123")
        self.session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a fintech landing page",
            output_type="react",
            files=[
                {"name": "src/main.js", "content": "const result = obj.property;"},
            ],
            status="done",
            build_status="failed",
            verification_status="failed",
            runtime_provider="webcontainer",
            runtime_status="failed",
        )

    @patch("builder.services.error_fixer.ErrorFixer.get_ai_fix")
    def test_auto_fix_rejects_unsafe_target_paths(self, mock_get_ai_fix):
        mock_get_ai_fix.return_value = {
            "explanation": "Attempt to overwrite unrelated file.",
            "fixed_code": "malicious",
            "files_to_update": ["../../manage.py"],
        }

        response = self.client.post(
            reverse("session-runtime-auto-fix", args=[self.session.id]),
            data=json.dumps(
                {
                    "error_message": "TypeError: boom",
                    "file_path": "../../manage.py",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "UNSAFE_FIX_TARGET")
