#!/bin/bash

# Скрипт для запуска агента закупок каждый час
# Использование: добавьте в crontab: 0 * * * * /path/to/start_hourly.sh

# Путь к проекту
PROJECT_DIR="/home/denis/horien-purchase-agent"

# Переходим в директорию проекта
cd "$PROJECT_DIR"

# Логируем запуск
echo "$(date): Запуск агента закупок Horiens" >> logs/hourly.log

# Запускаем контейнер
docker compose up --build >> logs/hourly.log 2>&1

# Логируем завершение
echo "$(date): Агент закупок завершил работу" >> logs/hourly.log
echo "----------------------------------------" >> logs/hourly.log 