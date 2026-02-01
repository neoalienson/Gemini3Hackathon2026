# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies: install google-genai and google-adk first so pip
# does not backtrack to ancient versions (e.g. google-adk 0.0.1 without google.adk module)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "google-genai>=1.30.0" "google-adk>=1.15.0" && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run uses PORT environment variable)
EXPOSE 8080

# Run the application using uvicorn
# Cloud Run will set the PORT environment variable
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
