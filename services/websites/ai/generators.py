import requests
import json
import logging

logger = logging.getLogger(__name__)


class WebsiteGenerator:
    def __init__(
        self,
        model="llama3.1:8b",
        url="http://ollama-techspacehub:11434/api/generate",
    ):
        self.model = model
        self.url = url

    def generate(self, prompt):
        """
        Sends prompt to Ollama and returns generated content.
        """
        logger.info(f"Calling Ollama with model {self.model}")
        payload = {"model": self.model, "prompt": prompt, "stream": False}

        try:
            # Placeholder for actual Ollama call
            # response = requests.post(self.url, json=payload, timeout=60)
            # return response.json().get('response')

            # Dummy response
            return "<html><body><h1>Generated Website</h1><p>Your AI website content goes here.</p></body></html>"
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            raise e

    def build_prompt(self, brief, template_id=None):
        prompt = f"Create a professional website based on this brief: {brief}. "
        if template_id:
            prompt += f"Use the design style of template {template_id}. "
        prompt += "Return only valid HTML, CSS, and JS."
        return prompt
