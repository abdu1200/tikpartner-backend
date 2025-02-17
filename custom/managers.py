from django.contrib.auth.models import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        if not password:
            raise ValueError("The Password field must be set")

        email = self.normalize_email(email)
        extra_fields.setdefault('username', email) #this is for when creating a normal user, if no username is provided, the email value is used as the username field in the database. it has nothing to do with the idea of "USERNAME_FIELD for authentication"
        
        user = self.model(email=email, **extra_fields) #This line creates a new user instance using Django's custom user model, setting the email and any extra fields. and this is ORM by the way
        user.set_password(password)  # Hashes the password securely
        user.save(using=self._db)  #ORM to save the user data
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not username:
            raise ValueError("Superusers must have a username")

        return self.create_user(email, password, username=username, **extra_fields)







"""
- BaseUserManager is the manager for the AbstractUser model, and it manages or handles user creation properly by defining how users and superusers should be created, ensuring things like email normalization and password hashing.
- In the normal users creation, users must provide email and password(see in the above code), and that the email is set to the USERNAME_FIELD for authentication(b/c of USERNAME_FIELD = 'email' in the custom user).
- In the superusers creation, users must provide not only email and password, but also username(b/c of REQUIRED_FIELDS = ['username'] in the custom model). and still the email is the one that is set to the USERNAME_FIELD for authentication.
- For superusers, the authentication mechanism remains the same because USERNAME_FIELD = 'email' applies globally to all users, including superusers.
- So, even though superusers must provide a username during creation, they still log in using their email and password, just like regular users.
"""

"""
- Email normalization means converting an email address into a standardized format to ensure consistency and avoid duplicate entries(in the db) due to case differences.
- normalize_email() in BaseUserManager converts parts after '@' to lower case and keeps parts before '@' unchanged. Because 'User.Example@GMAIL.com' and 'user.example@gmail.com' are exactly the same

- Password hashing is the process of converting a plain-text password into an irreversible, encrypted format before storing it in the database.
- Django provides a built-in method called set_password() that automatically hashes passwords using a secure hashing algorithm.
"""