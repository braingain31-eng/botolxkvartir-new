# Use the official lightweight Python image.
FROM python:3.11-slim

# Allow logs to appear immediately
ENV PYTHONUNBUFFERED True

# App directory
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Предзагружаем модель Whisper
RUN python -c "from faster_whisper import WhisperModel; \
    print('Скачиваем модель base...'); \
    WhisperModel('base', device='cpu', compute_type='int8')"

# Copy application code
COPY . .

# Copy Telethon session (after local authorization)
COPY session_telegram_parser* /app/

# Gunicorn settings (переопределяй в Cloud Run через env vars)
ENV GUNICORN_CMD_ARGS "--workers=2 --threads=4 --timeout=120 --keep-alive=75"

# Run the web server
CMD ["sh", "-c", "gunicorn $GUNICORN_CMD_ARGS -b 0.0.0.0:8080 main:app"]
# Run the web server on container startup.
# Use gunicorn for production.
# The following command assumes that your Flask app object is named 'app' in 'main.py'.
# For example: app = Flask(__name__)
# CMD ["gunicorn", "--workers", "4", "--threads", "4", "-b", "0.0.0.0:8080", "main:app"]
# CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "120", "--keep-alive", "75", "-b", "0.0.0.0:8080", "main:app"]
