import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import services.websites.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybercraft.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            services.websites.routing.websocket_urlpatterns
        )
    ),
})
