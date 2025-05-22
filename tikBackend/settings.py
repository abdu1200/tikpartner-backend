"""
Django settings for tikBackend project.

- load_dotenv() - only loads environment variables but does not automatically parse the database URL.
- environ - simplifies the process by converting the DATABASE_URL string into a proper Django database settings dictionary.

- running 'python manage.py dbshell' confirms that Django is successfully connected to the database. 
when you run the command ,If it opens the database shell (psql for PostgreSQL), it means Django is successfully connected and can access the database defined in the settings.py
- in the DB shell (railway=#), you can only run SQL commands (e.g., SELECT * FROM...)    -to quit the shell, use '\q'

- when i deploy my database on railway and then connect it with my local django project and migrate the models to it and also create a superuser for that deployed database, 
and now when i deploy my django backend on render, i can get to use the admin credentials on the live backend server

- use 'pip freeze > requirements.txt' to generate requirements.txt, a file that contains all your project dependencies(python package names)
and docker will use them to install packages inside a container

"""
from pathlib import Path
import os
from datetime import timedelta
import cloudinary
import cloudinary.uploader
import cloudinary.api
# import cloudinary_storage


                                     
                     ######  
from dotenv import load_dotenv 
import environ  #for database_url b/c it automates the dictionary parsing and everything

# Load .env file .....and then we will use os.getenv() to get the loaded variables
load_dotenv()

# Initialize django-environ
env = environ.Env()

# Read environment variables from the .env file
environ.Env.read_env()  


DATABASES = {
    'default': env.db("DATABASE_PUBLIC_URL")
}

# Ensure SSL for secure connection
DATABASES['default']['OPTIONS'] = {
    'sslmode': 'require',  # Enforces SSL for Railway
}



### Build paths inside the project like this: BASE_DIR / 'subdir'.        ######
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = 'django-insecure-tna8a!z9j&5dhrzaj7=jwn6z^gi3fnxujxk7(bvcw6e$+^hi4v'
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
#DEBUG = True

# '.onrender.com',  
ALLOWED_HOSTS = [
    'tikbackend.onrender.com',
    'localhost',
    '127.0.0.1',
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tikPartner',
    'custom',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    'uvicorn',
    'cloudinary',
    'cloudinary_storage',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tikBackend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

#WSGI_APPLICATION = 'tikBackend.wsgi.application'
ASGI_APPLICATION = 'tikBackend.asgi.application'


# Channel Layers - Use in-memory for development
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels.layers.InMemoryChannelLayer',
#     },
# }


#Configure Channel Layers for produuction (using Redis)   # Configuring django channels to use redis as a message broker
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],  # Ensure Redis is running
        },
    },
}



# Database
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'tikDatabase',
#         'USER': 'postgres',
#         'PASSWORD': 'm0md1dfa',
#         'HOST': 'localhost',
#         'PORT': '5432',  # default PostgreSQL port
#     }
# }



# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # this is Where 'collectstatic' will put files

# when you run 'python manage.py collectstatic', it will gather all the static files from your installed apps and place them in your STATIC_ROOT directory so they can be properly served.
# so dependencies that got static files, for eg. 'rest_framework', its static files like css&js files for styling the rest_framework browsable api will be stored in the 'staticfiles' directory.
# bad browsable api look = the CSS and JavaScript files that style the REST framework's browsable API are missing.
# so the 404 errors indicate that your Django REST framework static files aren't being served properly, which is why your interface doesn't look as expected. 



# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


AUTH_USER_MODEL = 'custom.CustomUser'   #replacing the default django user model with the new custom one

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    
}

SIMPLE_JWT = {
    #'AUTH_HEADER_TYPES': ('JWT',),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=3),
}

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_CREDENTIALS = True




EMAIL_HOST = 'smtp.gmail.com'    #we're using Gmail's email(smtp) server for sending emails from our django app
EMAIL_PORT = 587    # Port for TLS  
EMAIL_USE_TLS = True    # Use TLS for security
EMAIL_HOST_USER = "abdukmom03@gmail.com"     # Your Gmail address
EMAIL_HOST_PASSWORD = "zhvy gnbx puqo rnzy"   # Your Gmail app password (use app password for Gmail)

# Email backend configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER   # This will be used as the default "from" email in sent emails




STRIPE_SECRET_KEY = 'sk_test_51PPN5NRt8NVEmh7TUCUTWM3Zc1y4GZg4REs2knS1PTgj3ZG0pCURneFxbhkjbIBwT5G5puYbTG7Gvy15p78raaUt00cBkYj4Mi'
STRIPE_PUBLISHABLE_KEY = 'pk_test_51PPN5NRt8NVEmh7T5gwdm6cP4qAfXlKy8pwcMiEb4NtuBnGL8w9farKjO5t4SqBzFeT7O5e1j21KkCTrLjOFdhQA00LakRPJSZ'
# STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
# STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY') 



TIKTOK_CLIENT_KEY = 'sbaweuralgopknrhuo'
TIKTOK_CLIENT_SECRET = 'Kr3WE2CbqjhID2gsDoty7DpMEGT3wA05'
TIKTOK_REDIRECT_URI = 'https://tikfrontend-latest.onrender.com/InfluencerSignup'



# Cloudinary credentials
# CLOUDINARY_STORAGE = {
#     'CLOUD_NAME': 'dbahlieut',
#     'API_KEY': '853862792599424',
#     'API_SECRET': 'J7yRB_qkLa-kOXZ_gSEA9V-k27s',
# }

# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


cloudinary.config(
    cloud_name="dbahlieut",
    api_key="853862792599424",
    api_secret="J7yRB_qkLa-kOXZ_gSEA9V-k27s",
)
