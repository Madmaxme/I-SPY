FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install openai

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploaded_faces face_search_results/temp_images face_search_results/unknown/images

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "backend_server.py"]