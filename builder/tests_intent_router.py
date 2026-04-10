import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from builder.models import GenerationSession
from builder.services.credit_service import get_or_create_credits
from builder.services.prompt_validator import PromptValidator

User = get_user_model()


class PromptIntentRouterTestCase(TestCase):
    def setUp(self):
        self.validator = PromptValidator()

    def test_small_talk_is_not_treated_as_generation(self):
        result = self.validator.route("hi")

        self.assertEqual(result["intent"], "small_talk")
        self.assertFalse(result["should_generate"])
        self.assertIn("Hello", result["response"])

    def test_new_website_request_is_routed_to_build(self):
        result = self.validator.route("Build a portfolio website for a photographer")

        self.assertEqual(result["intent"], "build_new")
        self.assertTrue(result["should_generate"])

    def test_existing_project_change_is_routed_to_edit(self):
        result = self.validator.route(
            "Make the hero section blue and add testimonials",
            has_existing_project=True,
        )

        self.assertEqual(result["intent"], "edit_existing")
        self.assertTrue(result["should_generate"])

    def test_ambiguous_help_is_not_auto_generated(self):
        result = self.validator.route("What can you do here?")

        self.assertEqual(result["intent"], "general_help")
        self.assertFalse(result["should_generate"])

    @patch("builder.services.prompt_validator.PromptValidator._call_classifier")
    def test_ai_fallback_route_is_normalized(self, mock_classifier):
        mock_classifier.return_value = {
            "intent": "fix_error",
            "reason": "The user wants debugging help.",
            "response": "I can help debug that issue.",
            "suggestion": "Share the build log.",
            "should_generate": True,
        }

        result = self.validator.route("The preview crashes after I click the menu")

        self.assertEqual(result["intent"], "fix_error")
        self.assertTrue(result["should_generate"])

    @patch("builder.services.prompt_validator.OpenRouterBuilderClient.create_chat_completion")
    def test_classifier_parses_fenced_json_from_openrouter_helper(self, mock_completion):
        mock_completion.return_value = """```json
{
  "intent": "general_help",
  "reason": "User is asking a question.",
  "response": "I can explain how the builder works.",
  "suggestion": "Ask me to build a landing page when you're ready.",
  "should_generate": false
}
```"""

        result = self.validator._call_classifier("How does this builder work?")

        self.assertEqual(result["intent"], "general_help")
        self.assertFalse(result["should_generate"])
        self.assertIn("builder works", result["response"].lower())


class BuilderIntentEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="intent-user",
            password="password123",
        )
        self.client.login(username="intent-user", password="password123")

    def test_validate_prompt_returns_rich_intent_payload(self):
        response = self.client.post(
            reverse("validate-prompt"),
            data=json.dumps({"prompt": "hi"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "small_talk")
        self.assertFalse(data["should_generate"])
        self.assertIn("response", data)

    def test_assistant_message_routes_small_talk(self):
        response = self.client.post(
            reverse("assistant-message"),
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "small_talk")
        self.assertFalse(data["should_generate"])
        self.assertIn("help you with your website", data["response"].lower())

    def test_assistant_message_routes_build_request(self):
        response = self.client.post(
            reverse("assistant-message"),
            data=json.dumps({"message": "Create a landing page for a coffee shop"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "build_new")
        self.assertTrue(data["should_generate"])

    def test_generate_rejects_small_talk_without_using_credits(self):
        credits, _ = get_or_create_credits(self.user)
        before = credits.credits

        response = self.client.post(
            reverse("generate"),
            data=json.dumps(
                {
                    "prompt": "hi",
                    "output_type": "react",
                    "model": "trinity",
                }
            ),
            content_type="application/json",
        )

        credits.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(credits.credits, before)
        self.assertEqual(GenerationSession.objects.count(), 0)
        self.assertEqual(response.json()["error"], "NON_BUILD_INTENT")

    def test_chat_returns_normal_response_for_small_talk_without_using_credits(self):
        credits, _ = get_or_create_credits(self.user)
        before = credits.credits
        session = GenerationSession.objects.create(
            user=self.user,
            prompt="Build a portfolio site",
            output_type="react",
            files=[{"name": "src/App.jsx", "content": "export default function App(){return null}"}],
            status="done",
        )

        response = self.client.post(
            reverse("session-chat", args=[session.id]),
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        credits.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "small_talk")
        self.assertFalse(data["should_generate"])
        self.assertEqual(credits.credits, before)
