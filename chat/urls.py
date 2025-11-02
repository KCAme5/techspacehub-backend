from django.urls import path
from .views import chat, test_models, test_gemini_working, chat_stream

urlpatterns = [
    path("chat/", chat, name="chat"),
    path("test-models/", test_models, name="test_gemini"),
    path("test-gemini-working/", test_gemini_working, name="test_gemini"),
    path("chat/stream/", chat_stream, name="chat_stream"),
]
