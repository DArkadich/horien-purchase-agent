FROM python:3.10-slim

WORKDIR /app

# Устанавливаем cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создаем скрипт запуска
RUN echo '#!/bin/bash\n\
while true; do\n\
    echo "$(date): Запуск агента закупок..."\n\
    python main.py\n\
    echo "$(date): Агент завершил работу, ожидание 1 час..."\n\
    sleep 3600\n\
done' > /app/start.sh

RUN chmod +x /app/start.sh

# Создание пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Точка входа
CMD ["/app/start.sh"] 