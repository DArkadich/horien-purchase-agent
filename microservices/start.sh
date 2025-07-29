#!/bin/bash

# Скрипт для запуска микросервисов

echo "🚀 Запуск микросервисов Ozon..."

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен"
    exit 1
fi

# Создаем необходимые директории
echo "📁 Создание директорий..."
mkdir -p logs
mkdir -p data
mkdir -p nginx/ssl

# Копируем файлы из основного проекта
echo "📋 Копирование файлов..."
cp ../ozon_api.py ./
cp ../cache_manager.py ./
cp ../api_metrics.py ./
cp ../api_monitor.py ./
cp ../forecast.py ./
cp ../telegram_notify.py ./
cp ../sheets.py ./
cp ../config.py ./

# Создаем .env файл если его нет
if [ ! -f .env ]; then
    echo "📝 Создание .env файла..."
    cat > .env << EOF
# Ozon API настройки
OZON_CLIENT_ID=your_client_id
OZON_API_KEY=your_api_key
OZON_BASE_URL=https://api-seller.ozon.ru

# Telegram настройки
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Google Sheets настройки
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
SPREADSHEET_ID=your_spreadsheet_id

# Настройки базы данных
DATABASE_URL=postgresql://ozon_user:ozon_password@postgres:5432/ozon_microservices

# Настройки Redis
REDIS_URL=redis://redis:6379

# Настройки RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Настройки мониторинга
API_MONITORING_ENABLED=true
API_MONITORING_INTERVAL=300
API_HEALTHY_THRESHOLD=200
API_DEGRADED_THRESHOLD=1000

# Настройки метрик
API_METRICS_ENABLED=true
API_METRICS_RETENTION_DAYS=30
API_METRICS_RESPONSE_TIME_THRESHOLD=5000
API_METRICS_ERROR_RATE_THRESHOLD=5.0
API_METRICS_SUCCESS_RATE_THRESHOLD=95.0
EOF
    echo "⚠️  Отредактируйте .env файл с вашими настройками"
fi

# Останавливаем существующие контейнеры
echo "🛑 Остановка существующих контейнеров..."
docker-compose down

# Собираем и запускаем сервисы
echo "🔨 Сборка и запуск сервисов..."
docker-compose up --build -d

# Ждем запуска сервисов
echo "⏳ Ожидание запуска сервисов..."
sleep 30

# Проверяем статус сервисов
echo "🔍 Проверка статуса сервисов..."
docker-compose ps

# Проверяем здоровье API Gateway
echo "🏥 Проверка здоровья API Gateway..."
curl -f http://localhost:8000/health || echo "❌ API Gateway недоступен"

echo ""
echo "✅ Микросервисы запущены!"
echo ""
echo "📊 Доступные сервисы:"
echo "  - API Gateway: http://localhost:8000"
echo "  - Data Service: http://localhost:8001"
echo "  - Forecast Service: http://localhost:8002"
echo "  - Notification Service: http://localhost:8003"
echo "  - Monitoring Service: http://localhost:8004"
echo "  - Storage Service: http://localhost:8005"
echo "  - Nginx: http://localhost:80"
echo ""
echo "🔧 Управление:"
echo "  - Просмотр логов: docker-compose logs -f"
echo "  - Остановка: docker-compose down"
echo "  - Перезапуск: docker-compose restart"
echo ""
echo "📈 Мониторинг:"
echo "  - RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "  - Redis: localhost:6379"
echo "  - PostgreSQL: localhost:5432" 