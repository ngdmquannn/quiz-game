# server/Dockerfile

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy server code and question bank
COPY server.py .
COPY questions_linux.json .
COPY questions_networking.json .
COPY questions_python.json .

# Expose the quiz port
EXPOSE 8888

# Start container in idle mode — wait for admin GUI to run server.py
CMD ["python", "server.py"]
