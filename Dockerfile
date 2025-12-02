FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Это критично — имя файла и переменной
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "main:app"]