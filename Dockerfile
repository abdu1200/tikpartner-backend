# Use an official Python runtime as base
FROM python:3.10

# Set the working directory
WORKDIR /app

#To Set environment variable for Django settings, to be used by asgi.py inside of a docker container
ENV DJANGO_SETTINGS_MODULE=tikBackend.settings

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the default Django port
EXPOSE 8000

# Run migrations and start server
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8000", "tikBackend.asgi:application"]
#CMD ["gunicorn", "--bind", "0.0.0.0:8000", "tikBackend.wsgi:application"]







##This below description is done for uvicorn, and its exactly the same for Gunicorn just replace '--host' with '--bind' and a little bit of syntax d/ce when using CMD.

# 'uvicorn' is the ASGI server responsible for handling both HTTP and WebSocket requests in your Django app.

# 'tikBackend.asgi:application' - specifices the entrypoint(w/h is asgi.py) for uvicorn to run the django app
# Uvicorn doesn't directly navigate to the settings module(settings.py) to find your asgi.py file. Rather, you directly tell Uvicorn where your ASGI application(application) is with the CMD(tikBackend.asgi:application)
# and when asgi.py file is loaded, inside of asgi.py file, Django/uvicorn needs to know the settings module(settings.py) to use for configuring & running the application. so you put this: os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tikBackend.settings') inside of asgi.py
# we set "ENV DJANGO_SETTINGS_MODULE=tikBackend.settings" in the Dockerfile to ensure this environment variable is available throughout the container, w/h makes it to be accessible inside of asgi.py for the above line usecase 

# '--host 0.0.0.0:8000' - tells Uvicorn to listen on all network interfaces (0.0.0.0) and specifically on port 8000
# when you dockerize your project, your project is going to run inside of a docker container
# and when i bind/host 0.0.0.0:8000 to my django app(or to uvicorn that run my django app) w/h is going to be running inside of the container, now my app(uvicorn) can listen on all network interfaces (0.0.0.0) and specifically on port 8000.
# without that, my app(uvicorn) w/h is running inside of a container can only listen to '127.0.0.1', w/h makes it only accessible locally
# but now that we used '--host 0.0.0.0:8000', when you deploy the docker image on render and when render runs it on a docker container, my django app(uvicorn) can listen requests on https://tikbackend.onrender.com/





##In development

#when you run "python manage.py runserver", Django’s built-in WSGI server(or Django ) uses DJANGO_SETTINGS_MODULE from 'manage.py' to find 'settings.py'
#and then using WSGI_APPLICATION = 'tikBackend.wsgi.application', django will be able to find WSGI application entry point(wsgi.py & application)
#Django then loads and uses wsgi.py to handle HTTP requests

#If you're using Django Channels, Django Channels modifies the 'runserver' command to use the development ASGI server that can handle both HTTP and WebSocket requests.
#so when you run "python manage.py runserver", Django’s built-in ASGI server(or Django & django channels) uses DJANGO_SETTINGS_MODULE from 'manage.py' to find 'settings.py'
#and then using ASGI_APPLICATION = 'tikBackend.asgi.application', django & django channels will be able to find ASGI application entry point(asgi.py & application)
#Django(& django channels) then loads and uses asgi.py to handle both HTTP requests and Websocket requests


##Think of like

#django's production WSGI server = Gunicorn
#django's production ASGI server = Unicorn
#django's built-in development WSGI server = Django package
#django's built-in development ASGI server = Django package and Django Channels package



