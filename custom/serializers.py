from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode
from tikPartner.models import InfluencerProfile
from tikPartner.serializers import InfluencerProfileSerializer
from .user_serializers import CustomUserSerializer


#CustomUserSerializer was at the exact place before the CIRCULAR DEPENDENCY IMPORT error b/n tikPartner.serializers.py and custom.serializers.py


#Custom serializer for JWT authentication using email instead of username.
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
   
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    # def validate(self, attrs):
    #     email = attrs.get("email")
    #     password = attrs.get("password")

    #     user = authenticate(username=email, password=password)
    #     if not user:
    #         raise serializers.ValidationError({"detail": "Invalid credentials"})
    #     if not user.is_active:
    #         raise serializers.ValidationError({"detail": "User is inactive"})

    #     return super().validate(attrs)

    #this is to return the user profile(either InfluencerProfile or BrandProfile) with the access and refresh token
    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)     #user is a python instance
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials"})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "User is inactive"})

        # Get token data
        data = super().validate(attrs)   #data is a dictionary of access and refresh tokens

         # Check user type and fetch appropriate profile
        if user.user_type == 'influencer':
            try:
                profile = InfluencerProfile.objects.get(user=user)          #influencer_profile is a python instance
                profile_data = InfluencerProfileSerializer(profile).data    #profile_data is a dictionary
                data["profile_type"] = "influencer"
                data["profile"] = profile_data         # Attach profile info
            except InfluencerProfile.DoesNotExist:
                raise serializers.ValidationError({"detail": "Influencer profile not found"})
        elif user.user_type == 'brand':
            try:
                profile = BrandProfile.objects.get(user=user)
                profile_data = BrandProfileSerializer(profile).data
                data["profile_type"] = "brand"
                data["profile"] = profile_data
            except BrandProfile.DoesNotExist:
                raise serializers.ValidationError({"detail": "Brand profile not found"})
        else:
            # Handle admin users or any other user type without a profile
            user_data = CustomUserSerializer(user).data
            data["profile_type"] = "admin"
            data["profile"] = {"user": {}}   #this is to create a user dictionary inside of a profile dictionary b/c admin doesn't have a profile, it just has a user data
            data["profile"]["user"] = user_data
            

        return data    #this data dictionary is being returned to the view, then to be serialized to json and be returned to client






"""
 user = authenticate(username=email, password=password) - does the authentication, verifies if the user is actually in the db and if its password is correct(by the way it hashes the user input password and then compares it in the db)
 super().validate(attrs) - this calls the parent class's validate method(the default JWT logic) for generating and returning the JWT tokens (access and refresh), because in the custom serializer, we don't want to write the logic for generating and returning the tokens again, b/c its already done in the parent serializer.
 BTW, the parent class is TokenObtainPairSerializer
"""





User = get_user_model()

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()




class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:       #here this checks if the entered 'new_password' and 'confirm_password' are the same(match) 
            raise serializers.ValidationError({"error": "Passwords don't match"})
        
        try:
            uid =urlsafe_base64_decode(data['uid'])   #decode the user id
            user = User.objects.get(pk=uid)                        #get the user instance from the database using the user id 
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):     # 'User.DoesNotExist' might happen if an admin deletes the user before the user finished its password resetting(or midst of it)
            raise serializers.ValidationError({"error": "Invalid user ID"})

        if not PasswordResetTokenGenerator().check_token(user, data['token']):   #this happens when the password reset token generated for this specific user might have expired or it has already been used (so a person can not use the reset link sent his/her email more than once, it be invalid)  
            raise serializers.ValidationError({"error": "Invalid or expired token"})
        
        self.user = user    #here we set the user instance to 'self.user' to be accessed and used in the save method
        return data

    def save(self):
        self.user.set_password(self.validated_data['new_password'])    #this updates the user instance's password to the new password
        self.user.save()                                               #this saves the new data in the db
        return self.user