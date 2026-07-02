# ---- Frontend build stage (React + Vite) ----
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# vite build -> ../static/dashboard (ya'ni /static/dashboard)
RUN npm run build


# ---- Python / Django + bot stage ----
FROM python:3.12-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# React build natijasini frontend stage'dan olib kelamiz (collectstatic uchun)
COPY --from=frontend /static/dashboard /app/static/dashboard

# Create directories
RUN mkdir -p static staticfiles media

# Collect static (React dashboard ham shu yerda yig'iladi)
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || echo "Collectstatic skipped"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Default command - RUN_MODE ga qarab web/bot/both ishlaydi
CMD ["python", "start.py"]
