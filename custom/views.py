from django.shortcuts import render
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

#Custom JWT authentication view to log in using email and password.
class CustomTokenObtainPairView(TokenObtainPairView):

    serializer_class = CustomTokenObtainPairSerializer






"""
The steps

1,CustomTokenObtainPairView receives the request data(email and password from the client) and passes it to CustomTokenObtainPairSerializer.
2,CustomTokenObtainPairSerializer deserializes (parses) the data and validates it.
3,If valid, the authentication logic (checking if the user exists, verifying the password, etc.) happens inside the serializer.
4,If authenticated, the serializer generates access and refresh tokens and returns them as Python objects.
5,The view (CustomTokenObtainPairView) takes these tokens, serializes them into JSON, and sends them back to the client.

- So the 'CustomTokenObtainPairView' only handles the http requests (like the request/response logic) in which the logic for is inherited from TokenObtainPairView) 

"""