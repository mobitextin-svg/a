FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 8000
# Default command runs the web tier; the worker uses a different command
# (see docker-compose.yml).
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "mailsaas.wsgi:app"]
