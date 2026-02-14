# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
COPY pyproject.toml .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY . .

# Expose the port (Railway typically sets PORT env var, defaulting to 8000 here)
ENV PORT=8000
EXPOSE 8000

# Command to run the application
# We use the shell form to allow variable expansion for $PORT
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
