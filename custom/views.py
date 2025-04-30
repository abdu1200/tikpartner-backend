from django.shortcuts import render
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.core.mail import send_mail
from django.conf import settings
from .serializers import CustomTokenObtainPairSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer

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




User = get_user_model()

class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)      #this checks if there is a user with that email in the system
            token = PasswordResetTokenGenerator().make_token(user)    #this creates a password reset token for a specific user   
            uid = urlsafe_base64_encode(force_bytes(user.pk))         #this encodes the user id
            
            # In a real-world scenario, you would include a link to your frontend
            #reset_link = f"https://tikfrontend-latest.onrender.com/PasswordReset?uid={uid}&token={token}"

            # Check user_type and create appropriate reset link
            if user.user_type == 'influencer':
                reset_link = f"https://tikfrontend-latest.onrender.com/InfluencerPasswordReset?uid={uid}&token={token}"
            elif user.user_type == 'brand':
                reset_link = f"https://tikfrontend-latest.onrender.com/BrandPasswordReset?uid={uid}&token={token}"
            
            # Send email
            send_mail(
                'Reset your password',
                f'Click the link to reset your password: {reset_link}',
                settings.EMAIL_HOST_USER,    #the email to be sent 'from'
                [email],      #the email to be sent 'to'
                fail_silently=False,
            )
        except User.DoesNotExist:   
            # here, even if there is no user with the inputted email in the system, we don't reveal that for security reasons. 
            # B/c This prevents user enumeration attacks, where attackers could check to see which email addresses are registered with your service(in the system) by observing different responses from the password reset endpoint.
            pass
        
        return Response({"detail": "Password reset email has been sent."}, status=status.HTTP_200_OK)




class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)



"""
For the Password Reset and Login case, we used drf's APIView(class-based view) instead of drf's Viewset because:
1, Password reset and login are a very specific operations that only needs a few HTTP methods (typically POST). ViewSets are designed for operations that map neatly to CRUD operations on a resource(like auth/influencers/).
2, Specially the password reset flow involves two distinct endpoints with different behaviors (request and confirm), which don't naturally map to ViewSet actions.
3, These operations don't need the extra features that come with ViewSets like automatic URL routing through a router.
4, The implementation is cleaner and more straightforward with APIView for these specific use cases.
"""