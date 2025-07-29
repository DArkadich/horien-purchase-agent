FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY shared/ ./shared/
COPY forecast-service/ ./forecast-service/
COPY forecast.py ./
COPY config.py ./

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Открываем порт
EXPOSE 8002

# Запускаем приложение
CMD ["python", "forecast-service/main.py"] 