import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from tikPartner import routing as app_routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tikBackend.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),      # Handle HTTP requests
    "websocket": AuthMiddlewareStack(    # Handle WebSockets requests
        URLRouter(
            app_routing.websocket_urlpatterns
        )
    ),
})



"""
- ProtocolTypeRouter is used to give both HTTP and WebSocket support to the project.
- If the project only handles HTTP, the default get_asgi_application() is enough, like the one is the wsgi.py

- AuthMiddlewareStack is used if you need authentication for WebSocket connections (e.g., checking logged-in users).
- Without it, WebSocket requests won’t have access to Django’s authentication system.
so it ensures only authenticated users can connect to WebSockets. Without it, any user (even unauthenticated) could send messages.
"""