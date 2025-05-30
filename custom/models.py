from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import CustomUserManager
from cloudinary.models import CloudinaryField

# Create your models here.

class CustomUser(AbstractUser):  #This one is to be used in the settings.py by AUTH_USER_MODEL
    USER_TYPES = (
        ('influencer', 'Influencer'),
        ('brand', 'Brand'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    #is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bio = models.TextField(blank=True)
    profile_picture = CloudinaryField('profile-picture', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)


    USERNAME_FIELD = 'email'   #since django uses the field that is set to 'USERNAME_FIELD' as unique identifier(for authentication), it Tells Django to use email field for the USERNAME_FIELD instead of username field for authentication.
    REQUIRED_FIELDS = ['username']  #ensures 'username' is still required when creating a superuser.

    objects = CustomUserManager()

    def __str__(self):
        return self.email





"""
"objects = CustomUserManager()" - CustomUserManager is being instantiated and set to 'objects' in the custom user model, so that the manager(for handling the user creation) for the CustomUser is 'CustomUserManager()', otherwise the CustomUser uses the default UserManager() w/h expects username field as a must to be provided instead of email field
"""



    