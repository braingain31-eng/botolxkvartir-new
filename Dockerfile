# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Предзагружаем модель Whisper (важно ДО копирования кода!)
RUN python -c "from faster_whisper import WhisperModel; \
    print('Скачиваем модель base...'); \
    WhisperModel('base', device='cpu', compute_type='int8')"

# Копируем код
COPY . .

# Run the web server on container startup.
# Use gunicorn for production.
# The following command assumes that your Flask app object is named 'app' in 'main.py'.
# For example: app = Flask(__name__)
CMD ["gunicorn", "--workers", "4", "--threads", "4", "-b", "0.0.0.0:8080", "main:app"]
