FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY shared/ ./shared/
COPY notification-service/ ./notification-service/
COPY telegram_notify.py ./
COPY config.py ./

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Открываем порт
EXPOSE 8003

# Запускаем приложение
CMD ["python", "notification-service/main.py"] 