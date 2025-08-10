FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для научных библиотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libatlas-base-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем общие зависимости
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем исходники сервиса
COPY ./ml-service /app/ml-service
COPY ./shared /app/shared

ENV PYTHONPATH=/app

EXPOSE 8006

CMD ["python", "ml-service/main.py"]


