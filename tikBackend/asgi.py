import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tikBackend.settings')

#initialize django first(like initializing and loading all apps & their dependencies(packages))
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()


#now you can use app's functionalities(like models, routing) and also package's(like ProtocolTypeRouter)
from channels.routing import ProtocolTypeRouter, URLRouter
#from channels.auth import AuthMiddlewareStack
from tikPartner.middleware import TokenAuthMiddleware  # Import your custom middleware instead of AuthMiddlwareStack
from tikPartner.routing import websocket_urlpatterns
from channels.security.websocket import AllowedHostsOriginValidator
# when we make an http request, AuthMiddlewareStack allows us to authenticate a user using its JWT token from the authorization header of the request.
# when we make WebSocket connection, TokenAuthMiddleware allows us to authenticate a user using its JWT token from the websocketURL.
# so when we make a websocket connection, this middleware will extract the token from the WebSocket URL query parameters and authenticate the user accordingly.
# so it ensures only authenticated users can connect to WebSockets. Bcuz without it, any user (even unauthenticated) could send messages.


application = ProtocolTypeRouter({       # ASGI application entry point 
    "http": django_asgi_app,             # Handle HTTP requests
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddleware(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})



"""
- ProtocolTypeRouter is used to give both HTTP and WebSocket support to the project.
- If the project only handles HTTP, the default get_asgi_application() is enough, like the one is the wsgi.py

"""





