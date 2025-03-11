# Use an official Python runtime as base
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the default Django port
EXPOSE 8000

# Run migrations and start server
CMD ["uvicorn", "--bind", "0.0.0.0:8000", "tikBackend.asgi:application"]







# uvicorn is the ASGI server responsible for handling both HTTP and WebSocket requests in your Django app.
# 'tikBackend.asgi:application' - specifices the entrypoint(w/h is asgi.py) to uvicorn to run the django app
# '--bind 0.0.0.0:8000' - tells Uvicorn to listen on all network interfaces (0.0.0.0) and specifically on port 8000

# when you dockerize your project, your project is going to run inside of a docker container
# and when i bind 0.0.0.0:8000 to my django app(or to uvicorn that run my django app) w/h is going to be running inside of the container, now my app(uvicorn) can listen on all network interfaces (0.0.0.0) and specifically on port 8000.
# without that, my app(uvicorn) w/h is running inside of a container can only listen to '127.0.0.1', w/h makes it only accessible locally

# but now that we used '--bin 0.0.0.0:8000', when you deploy the docker image on render and when render runs it on a docker container, my django app(uvicorn) can listen requests on https://tikbackend.onrender.com/
