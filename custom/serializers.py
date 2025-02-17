from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 
                  'user_type', 'is_verified', 'bio', 'profile_picture', 'location', 'password']
        extra_kwargs = {
            'username': {'validators': []},  # Remove unique validator # this ONLY removes the unique validator applied by Django's 'unique=True' constraint on the model
            'email': {'validators': []}      # Remove unique validator  # it doesn't affect Required field validation and Field type validation(like valid email format)
        }

    
    def validate_username(self, value):     # value is the username value in the deserialized user dictionary
        """Only validate uniqueness for new users."""
        if self.instance is None and CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        """Only validate uniqueness for new users."""
        if self.instance is None and CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value



    #THE BASIC CREATION FLOW

    # def create(self, validated_data):
    #     user = get_user_model().objects.create_user(
    #         username=validated_data['username'],
    #         email=validated_data['email'],
    #         first_name=validated_data.get('first_name', ''),
    #         last_name=validated_data.get('last_name', ''),
    #         phone_number=validated_data.get('phone_number', ''),
    #         user_type=validated_data['user_type'],
    #         password=validated_data['password']
    #     )
    #     return user

    # def update(self, instance, validated_data):
    #     instance.username = validated_data.get('username', instance.username)
    #     instance.email = validated_data.get('email', instance.email)
    #     instance.first_name = validated_data.get('first_name', instance.first_name)
    #     instance.last_name = validated_data.get('last_name', instance.last_name)
    #     instance.phone_number = validated_data.get('phone_number', instance.phone_number)
    #     instance.bio = validated_data.get('bio', instance.bio)
    #     instance.location = validated_data.get('location', instance.location)
    #     instance.set_password(validated_data.get('password', instance.password))  #to hash the new password if there is one
        
    #     # Ensure the profile picture is only updated if provided
    #     profile_picture = validated_data.get('profile_picture', None)
    #     if profile_picture:
    #         instance.profile_picture = profile_picture
            
    #     instance.save()

    #     return instance





"""
There are two types of instance creation in the db using ORM:

- user = User.objects.create( email = validated_data['email'],... )

- user = User( email = validated_data['email'],... )
  user.save() 

  or instance.save() like for the above update case 
"""


"""
- The actual user creation happens in CustomUserManager, specifically in the create_user and create_superuser methods.
- In CustomUserSerializer, specifically in the create() method, the validated user data is passed to the CustomUserManager like this ' get_user_model().objects.create_user(**validated_data) '
and then the manager handles the actual creation and saving of the user in the database.
- as you see the create_user() method of the CustomUserManager is being called in the serializer
- so the create method in CustomUserSerializer is responsible for calling that manager inside the serializer.
- and so the actual user creation logic is handled in CustomUserManager.
"""



#Custom serializer for JWT authentication using email instead of username.
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
   
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials"})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "User is inactive"})

        return super().validate(attrs)


"""
 user = authenticate(username=email, password=password) - does the authentication, verifies if the user is actually in the db and if its password is correct(by the way it hashes the user input password and then compares it in the db)
 super().validate(attrs) - this calls the parent class's validate method(the default JWT logic) for generating and returning the JWT tokens (access and refresh), because in the custom serializer, we don't want to write the logic for generating and returning the tokens again, b/c its already done in the parent serializer.
 BTW, the parent class is TokenObtainPairSerializer
"""