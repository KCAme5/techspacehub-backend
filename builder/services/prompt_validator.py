"""
builder/services/prompt_validator.py
Validates that user prompts are actually requesting website generation,
not random chat messages.
"""

import json
import logging
from django.conf import settings
from ..ai.stepfun_client import OpenRouterBuilderClient

logger = logging.getLogger(__name__)

class PromptValidator:
    """
    Uses Claude to classify if a prompt is a valid website-building request.
    Returns: { is_valid: bool, reason: str, suggestion: str }
    """

    VALIDATION_PROMPT = """
You are a website builder intent classifier. Your job is to determine if a user's message is actually requesting a website to be generated.

VALID requests include:
- "Create a portfolio site for a photographer"
- "Build a landing page for my coffee shop"
- "Design a blog for my travel stories"
- "Make an e-commerce site for selling handmade jewelry"
- "Personal resume website"
- "Build a restaurant menu site"

INVALID requests include:
- "hi"
- "hello"
- "what's up"
- "how are you"
- "tell me a joke"
- "what time is it"
- "help me with math"
- "write a poem"
- "tell me about Python"

User prompt: "{prompt}"

Respond with ONLY valid JSON (no markdown, no extra text):
{{
    "is_valid": true/false,
    "reason": "brief explanation (1 sentence)",
    "suggestion": "if invalid, suggest a valid prompt example"
}}
"""

    def __init__(self):
        self.client = OpenRouterBuilderClient(model='claude-3.5-sonnet')

    def validate(self, prompt: str) -> dict:
        """
        Validate if prompt is a website-building request.
        
        Returns:
        {{
            "is_valid": bool,
            "reason": str,
            "suggestion": str (only if invalid)
        }}
        """
        if not prompt or len(prompt.strip()) < 3:
            return {
                "is_valid": False,
                "reason": "Prompt is too short",
                "suggestion": "Try: 'Create a landing page for my coffee shop'"
            }

        # Quick heuristic check first (saves API cost)
        if self._is_obviously_invalid(prompt):
            return {
                "is_valid": False,
                "reason": "This doesn't sound like a website request",
                "suggestion": "Try: 'Build a portfolio site for my photography business'"
            }

        # Use AI for edge cases
        try:
            validation_msg = self.VALIDATION_PROMPT.format(prompt=prompt)
            response = self._call_classifier(validation_msg)
            return response
        except Exception as e:
            logger.error(f"Validation failed: {e}. Defaulting to valid.")
            # On error, allow the request (don't block user)
            return {"is_valid": True, "reason": "Validation skipped (will retry on generation)"}

    def _is_obviously_invalid(self, prompt: str) -> bool:
        """Quick heuristic to catch obvious non-website requests"""
        invalid_keywords = [
            'how are you', 'what time', 'tell me a joke', 'hello', 'hi', 'what\'s up',
            'how do i', 'can you help', 'explain', 'write a poem', 'math problem',
            'who are you', 'what do you do', 'tell me about', 'translate',
            'summarize', 'correct this text', 'rewrite this', 'improve this'
        ]
        
        prompt_lower = prompt.lower()
        # If prompt is ONLY generic chat (no website keywords), flag it
        website_keywords = [
            'website', 'site', 'page', 'landing', 'portfolio', 'store', 'shop',
            'blog', 'app', 'build', 'create', 'design', 'generate', 'restaurant',
            'portfolio', 'ecommerce', 'e-commerce', 'resume', 'profile'
        ]
        
        has_chat_intent = any(kw in prompt_lower for kw in invalid_keywords)
        has_web_intent = any(kw in prompt_lower for kw in website_keywords)
        
        # If it has obvious chat intent and NO web keywords, it's invalid
        return has_chat_intent and not has_web_intent

    def _call_classifier(self, prompt: str) -> dict:
        """Call OpenRouter Claude to classify the prompt"""
        try:
            # This is a quick non-streaming call (unlike generation)
            response = self.client.client.chat.completions.create(
                model="openrouter/auto",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,  # Deterministic
                max_tokens=200,  # Short response
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            parsed = json.loads(response_text)
            return {
                "is_valid": parsed.get("is_valid", False),
                "reason": parsed.get("reason", "Unknown"),
                "suggestion": parsed.get("suggestion", "")
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation response: {e}")
            raise ValueError("Invalid validation response from AI")
        except Exception as e:
            logger.error(f"Classifier error: {e}")
            raise


# Singleton instance
_validator = None

def get_prompt_validator():
    global _validator
    if _validator is None:
        _validator = PromptValidator()
    return _validator
