FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# КЛЮЧЕВОЕ: используем main:app (не main_bot:app)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "main:app"]