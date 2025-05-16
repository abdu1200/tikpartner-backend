# middleware.py in your app directory
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()

class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        token_key = query_params.get('token', [None])[0]
        
        if token_key:
            scope['user'] = await self.get_user_from_token(token_key)
        else:
            scope['user'] = AnonymousUser()
            
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token_key):
        try:
            token = AccessToken(token_key)
            user_id = token.payload.get('user_id')
            return User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist):
            return AnonymousUser()