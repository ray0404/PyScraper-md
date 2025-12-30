# Use Python 3.12 slim as base
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install minimal system dependencies for Playwright installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (excluding dev group)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --extras dynamic --no-interaction --no-ansi --no-root

# Install Playwright and its system dependencies
# This command installs the browsers and the OS-level dependencies they need
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Install the project itself
RUN poetry install --only main --extras dynamic --no-interaction --no-ansi

# Expose the port
EXPOSE 8080

# Run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "md_scraper.web.app:app"]