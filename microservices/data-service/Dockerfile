FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY shared/ ./shared/
COPY data-service/ ./data-service/
COPY ozon_api.py ./
COPY cache_manager.py ./
COPY api_metrics.py ./
COPY config.py ./

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Открываем порт
EXPOSE 8001

# Запускаем приложение
CMD ["python", "data-service/main.py"] 