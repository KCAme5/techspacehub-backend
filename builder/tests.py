from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from builder.models import GenerationSession
import json

User = get_user_model()

class BuilderTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

    def test_generate_endpoint_exists(self):
        url = reverse('generate')
        # We don't want to actually call the LLM in a unit test, 
        # but we can verify the view is reachable and handles missing deps or auth.
        response = self.client.post(url, data=json.dumps({
            'prompt': 'A test website',
            'output_type': 'html',
            'model': 'llama'
        }), content_type='application/json')
        # Expected to fail due to missing credits or actual LLM call, 
        # but 404 would mean the route is wrong.
        self.assertNotEqual(response.status_code, 404)

    def test_session_list_exists(self):
        url = reverse('session-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
