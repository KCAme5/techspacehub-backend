import requests
import json
import logging

logger = logging.getLogger(__name__)


class WebsiteGenerator:
    def __init__(self, model="llama-3.3-70b-versatile"):
        from .groq_client import GroqWebsiteGenerator
        self.generator = GroqWebsiteGenerator(model=model)

    def generate(self, prompt):
        """
        Sends prompt to Groq and returns generated content.
        """
        return self.generator.generate_website(prompt)

    def build_prompt(self, brief, template_id=None):
        prompt = f"Create a professional website based on this brief: {brief}. "
        if template_id:
            prompt += f"Use the design style of template {template_id}. "
        prompt += "Return only valid HTML, CSS, and JS."
        return prompt

