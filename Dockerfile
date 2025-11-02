# Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency file
COPY requirements.txt /app/

# Install Python dependencies
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt


# Copy project files
COPY . /app/

# Expose Django port
EXPOSE 8000

# Wait for database and then run the app
CMD ["sh", "-c", "until nc -z db 5432; do echo 'Waiting for PostgreSQL...'; sleep 2; done; python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
