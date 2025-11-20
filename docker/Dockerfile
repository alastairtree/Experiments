# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements file and wheels
COPY requirements.txt .
COPY wheels/ /tmp/wheels/

# Install Python dependencies from local wheels
RUN pip install --no-index --find-links=/tmp/wheels -r requirements.txt && rm -rf /tmp/wheels

# Copy application code
COPY app.py .

# Expose port 5000
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "app.py"]
