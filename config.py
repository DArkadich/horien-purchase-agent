"""
Конфигурация приложения для агента закупок Horiens
"""

import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Только консольное логирование
    ]
)

logger = logging.getLogger(__name__)

# Минимальные партии для закупки по каждому SKU (MOQ - Minimum Order Quantity)
MINIMUM_ORDER_QUANTITIES = {
    # Растворы - конкретные SKU
    "360360": 24,
    "500500": 24,
    "120120": 48,
    # Добавьте другие SKU по необходимости
}

# Настройки прогнозирования
DAYS_FORECAST_SHORT = int(os.getenv('DAYS_FORECAST_SHORT', 30))
DAYS_FORECAST_LONG = int(os.getenv('DAYS_FORECAST_LONG', 45))
# Настройки анализа продаж
SALES_HISTORY_DAYS = int(os.getenv('SALES_HISTORY_DAYS', 180))

# Ozon API настройки
OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID')
OZON_API_KEY = os.getenv('OZON_API_KEY')
OZON_BASE_URL = os.getenv('OZON_BASE_URL', 'https://api-seller.ozon.ru')

# Настройки retry-логики для API
API_MAX_RETRIES = int(os.getenv('API_MAX_RETRIES', 3))
API_BASE_DELAY = float(os.getenv('API_BASE_DELAY', 2.0))
API_MAX_DELAY = float(os.getenv('API_MAX_DELAY', 30.0))
API_TIMEOUT = int(os.getenv('API_TIMEOUT', 30))

# Настройки кэширования
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
CACHE_DIR = os.getenv('CACHE_DIR', 'cache')
CACHE_DB_PATH = os.getenv('CACHE_DB_PATH', 'cache/cache.db')

# TTL для различных типов кэша (в часах)
CACHE_TTL_PRODUCTS = float(os.getenv('CACHE_TTL_PRODUCTS', 2.0))  # 2 часа
CACHE_TTL_SALES = float(os.getenv('CACHE_TTL_SALES', 1.0))        # 1 час
CACHE_TTL_STOCKS = float(os.getenv('CACHE_TTL_STOCKS', 0.5))      # 30 минут
CACHE_TTL_ANALYTICS = float(os.getenv('CACHE_TTL_ANALYTICS', 1.0)) # 1 час

# Настройки мониторинга API
API_MONITORING_ENABLED = os.getenv('API_MONITORING_ENABLED', 'true').lower() == 'true'
API_MONITORING_INTERVAL = int(os.getenv('API_MONITORING_INTERVAL', 300))  # 5 минут
API_HEALTHY_THRESHOLD = int(os.getenv('API_HEALTHY_THRESHOLD', 200))      # 200мс
API_DEGRADED_THRESHOLD = int(os.getenv('API_DEGRADED_THRESHOLD', 1000))   # 1000мс
API_MONITORING_DB_PATH = os.getenv('API_MONITORING_DB_PATH', 'data/api_health.db')

# Настройки метрик производительности API
API_METRICS_ENABLED = os.getenv('API_METRICS_ENABLED', 'true').lower() == 'true'
API_METRICS_DB_PATH = os.getenv('API_METRICS_DB_PATH', 'data/api_metrics.db')
API_METRICS_RETENTION_DAYS = int(os.getenv('API_METRICS_RETENTION_DAYS', 30))
API_METRICS_ALERT_THRESHOLDS = {
    'response_time_ms': int(os.getenv('API_METRICS_RESPONSE_TIME_THRESHOLD', 5000)),
    'error_rate_percent': float(os.getenv('API_METRICS_ERROR_RATE_THRESHOLD', 5.0)),
    'success_rate_percent': float(os.getenv('API_METRICS_SUCCESS_RATE_THRESHOLD', 95.0))
}

# Google Sheets настройки
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
GOOGLE_SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')

# Telegram настройки
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def validate_config() -> bool:
    """
    Проверяет корректность конфигурации
    """
    required_vars = [
        'OZON_API_KEY', 'OZON_CLIENT_ID', 'GOOGLE_SERVICE_ACCOUNT_JSON',
        'GOOGLE_SPREADSHEET_ID', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'
    ]
    
    missing_vars = []
    placeholder_vars = []
    
    for var in required_vars:
        value = globals().get(var)
        if not value:
            missing_vars.append(var)
        elif 'your_' in str(value) or 'here' in str(value):
            placeholder_vars.append(f"{var}={value}")
    
    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {missing_vars}")
        return False
    
    if placeholder_vars:
        logger.error(f"Обнаружены placeholder значения в конфигурации: {placeholder_vars}")
        logger.error("Пожалуйста, замените placeholder значения на реальные в файле .env")
        return False
    
    logger.info("Конфигурация загружена успешно")
    return True

def get_moq_for_sku(sku_name: str) -> int:
    """
    Возвращает минимальную партию для закупки по SKU
    """
    # Проверяем конкретные SKU
    if sku_name in MINIMUM_ORDER_QUANTITIES:
        return MINIMUM_ORDER_QUANTITIES[sku_name]
    
    # Правила для линз по паттернам SKU
    if len(sku_name) == 6 and sku_name.startswith('30'):
        # Однодневные линзы (6 цифр, начинаются на 30)
        return 1
    elif len(sku_name) == 5 and sku_name.startswith('6'):
        # Месячные линзы по 6 шт (5 цифр, начинаются на 6)
        return 1
    elif len(sku_name) == 5 and sku_name.startswith('3'):
        # Месячные линзы по 3 шт (5 цифр, начинаются на 3)
        return 1
    
    # По умолчанию для неизвестных SKU
    return 5 