# Base image with apt support
FROM python:3.10-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /app/

# Collect static files (safe during build)
RUN python manage.py collectstatic --noinput || echo "Collectstatic failed (expected if env vars missing)"

# Expose port (Render sets $PORT)
EXPOSE 8000

# Start server: run migrate + start Gunicorn
CMD bash -c "python manage.py migrate && gunicorn agentic_researcher.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 300"
