"""Intent routing for the AI website builder."""

import json
import logging
from ..ai.stepfun_client import OpenRouterBuilderClient

logger = logging.getLogger(__name__)


class PromptValidator:
    """
    Classifies incoming prompts into builder-specific intents.

    Primary intents:
    - small_talk
    - general_help
    - build_new
    - edit_existing
    - fix_error
    - unclear
    """

    CLASSIFICATION_PROMPT = """
You are an intent router for an AI website builder assistant.

Your job is to classify the user's message into exactly one intent:
- small_talk: greetings or casual conversation
- general_help: general questions that are not asking to build/edit code
- build_new: asking to create/generate a new website or frontend app
- edit_existing: asking to change an existing website/project
- fix_error: asking to debug or fix a code/build/runtime error
- unclear: related to building, but missing enough detail to proceed confidently

Context:
- has_existing_project: {has_existing_project}

User message:
"{prompt}"

Respond with ONLY valid JSON:
{{
  "intent": "small_talk|general_help|build_new|edit_existing|fix_error|unclear",
  "reason": "brief explanation",
  "response": "short assistant reply for the user",
  "suggestion": "optional follow-up suggestion",
  "should_generate": true/false
}}
"""

    SMALL_TALK_PATTERNS = (
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "what's up",
        "whats up",
    )
    BUILD_KEYWORDS = (
        "build",
        "create",
        "generate",
        "make",
        "design",
        "website",
        "landing page",
        "portfolio",
        "homepage",
        "frontend",
        "react app",
        "vite app",
        "site",
    )
    EDIT_KEYWORDS = (
        "edit",
        "update",
        "change",
        "modify",
        "redesign",
        "replace",
        "add",
        "remove",
        "make it",
        "make the",
        "make ",
        "turn it",
    )
    ERROR_KEYWORDS = (
        "fix error",
        "debug",
        "broken",
        "not working",
        "build failed",
        "runtime error",
        "console error",
        "syntax error",
        "typeerror",
        "referenceerror",
    )
    HELP_KEYWORDS = (
        "what can you do",
        "help me",
        "how does this work",
        "what is this",
        "explain",
        "tell me about",
        "why did you",
        "how do i",
        "what is the",
    )

    def __init__(self):
        self.client = OpenRouterBuilderClient(model="claude-3.5-sonnet")

    def route(self, prompt: str, has_existing_project: bool = False) -> dict:
        clean_prompt = (prompt or "").strip()
        if len(clean_prompt) < 2:
            return self._build_route(
                intent="unclear",
                reason="Prompt is too short to determine a build request.",
                response="Please tell me what kind of website or frontend page you want to build.",
                suggestion="Try: Build a landing page for my coffee shop.",
                should_generate=False,
            )

        obvious = self._classify_obvious_intent(clean_prompt, has_existing_project)
        if obvious:
            return obvious

        try:
            classification_prompt = self.CLASSIFICATION_PROMPT.format(
                prompt=clean_prompt,
                has_existing_project=str(has_existing_project).lower(),
            )
            return self._normalize_route(
                self._call_classifier(classification_prompt),
                fallback_prompt=clean_prompt,
                has_existing_project=has_existing_project,
            )
        except Exception as exc:
            logger.error("Intent classification failed: %s", exc)
            return self._build_route(
                intent="unclear",
                reason="Intent classification failed, so the request was not auto-routed into generation.",
                response="I can help with normal conversation or build a frontend website. Tell me what you want to create.",
                suggestion="Try: Build a React landing page for a law firm.",
                should_generate=False,
            )

    def validate(self, prompt: str, has_existing_project: bool = False) -> dict:
        route = self.route(prompt, has_existing_project=has_existing_project)
        return {
            "is_valid": route["should_generate"],
            "intent": route["intent"],
            "reason": route["reason"],
            "suggestion": route["suggestion"],
            "response": route["response"],
            "should_generate": route["should_generate"],
        }

    def _classify_obvious_intent(self, prompt: str, has_existing_project: bool) -> dict | None:
        prompt_lower = prompt.lower()

        if self._matches_any(prompt_lower, self.SMALL_TALK_PATTERNS):
            return self._build_route(
                intent="small_talk",
                reason="This is casual conversation, not a website build instruction.",
                response="Hello. I'm good. How can I help you with your website today?",
                suggestion="You can ask me to build a landing page, portfolio, or other frontend site.",
                should_generate=False,
            )

        if self._matches_any(prompt_lower, self.ERROR_KEYWORDS):
            return self._build_route(
                intent="fix_error",
                reason="The message is asking to diagnose or fix a code or build problem.",
                response="Send me the error or the broken session and I can work on the fix.",
                suggestion="Example: Fix the build error in my React landing page.",
                should_generate=True,
            )

        if self._matches_any(prompt_lower, self.HELP_KEYWORDS) and not self._matches_any(
            prompt_lower, self.BUILD_KEYWORDS
        ):
            return self._build_route(
                intent="general_help",
                reason="This is a general help question rather than a direct build instruction.",
                response="I can chat normally, help you plan a site, or generate and edit frontend code when you're ready.",
                suggestion="Try: Build a modern portfolio website for a UX designer.",
                should_generate=False,
            )

        has_build_keywords = self._matches_any(prompt_lower, self.BUILD_KEYWORDS)
        has_edit_keywords = self._matches_any(prompt_lower, self.EDIT_KEYWORDS)

        if has_existing_project and (
            has_edit_keywords
            or prompt_lower.startswith(("make ", "change ", "update ", "add ", "remove ", "replace ", "turn "))
        ):
            return self._build_route(
                intent="edit_existing",
                reason="The message refers to changing an existing project.",
                response="Understood. I can update the current project based on those instructions.",
                suggestion="Be specific about what should change, such as colors, sections, or layout.",
                should_generate=True,
            )

        if has_build_keywords and not has_existing_project:
            return self._build_route(
                intent="build_new",
                reason="The message is asking to create a new website or frontend app.",
                response="I can build that website for you.",
                suggestion="Include the business type, style, and key sections for a better first draft.",
                should_generate=True,
            )

        if has_build_keywords and has_existing_project and has_edit_keywords:
            return self._build_route(
                intent="edit_existing",
                reason="The message includes build language, but with an existing project it reads as an edit request.",
                response="I can apply those changes to the current project.",
                suggestion="Tell me exactly which sections or styles to update.",
                should_generate=True,
            )

        if any(word in prompt_lower for word in ("website", "page", "landing", "portfolio", "app")):
            return self._build_route(
                intent="unclear",
                reason="The request is related to websites, but it does not clearly ask to build or edit one yet.",
                response="I can help with that. Tell me whether you want a new site, an edit to an existing one, or debugging help.",
                suggestion="Try: Build a fintech landing page with a hero, pricing, and testimonials.",
                should_generate=False,
            )

        return None

    def _normalize_route(self, parsed: dict, fallback_prompt: str, has_existing_project: bool) -> dict:
        intent = parsed.get("intent", "unclear")
        if intent not in {"small_talk", "general_help", "build_new", "edit_existing", "fix_error", "unclear"}:
            intent = "unclear"

        should_generate = bool(parsed.get("should_generate", intent in {"build_new", "edit_existing", "fix_error"}))
        route = self._build_route(
            intent=intent,
            reason=parsed.get("reason", "Intent classified by AI."),
            response=parsed.get("response", ""),
            suggestion=parsed.get("suggestion", ""),
            should_generate=should_generate,
        )
        if not route["response"]:
            return self._classify_obvious_intent(fallback_prompt, has_existing_project) or route
        return route

    def _call_classifier(self, prompt: str) -> dict:
        response = self.client.client.chat.completions.create(
            model="openrouter/auto",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=250,
        )
        response_text = response.choices[0].message.content.strip()
        parsed = json.loads(response_text)
        return {
            "intent": parsed.get("intent", "unclear"),
            "reason": parsed.get("reason", "Unknown"),
            "response": parsed.get("response", ""),
            "suggestion": parsed.get("suggestion", ""),
            "should_generate": parsed.get("should_generate", False),
        }

    @staticmethod
    def _matches_any(prompt: str, phrases: tuple[str, ...]) -> bool:
        return any(phrase in prompt for phrase in phrases)

    @staticmethod
    def _build_route(intent: str, reason: str, response: str, suggestion: str, should_generate: bool) -> dict:
        return {
            "intent": intent,
            "reason": reason,
            "response": response,
            "suggestion": suggestion,
            "should_generate": should_generate,
            "is_valid": should_generate,
        }


_validator = None


def get_prompt_validator():
    global _validator
    if _validator is None:
        _validator = PromptValidator()
    return _validator
