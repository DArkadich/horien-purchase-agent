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
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Минимальные партии для закупки по каждому SKU (MOQ - Minimum Order Quantity)
MINIMUM_ORDER_QUANTITIES = {
    "линза -3.5": 5200,
    "линза -3.0": 4800,
    "линза -2.5": 4500,
    "линза -2.0": 4200,
    "линза -1.5": 4000,
    "линза -1.0": 3800,
    "линза -0.5": 3600,
    "линза +0.5": 3600,
    "линза +1.0": 3800,
    "линза +1.5": 4000,
    "линза +2.0": 4200,
    "линза +2.5": 4500,
    "линза +3.0": 4800,
    "линза +3.5": 5200,
    # Добавьте другие SKU по необходимости
}

# Настройки прогнозирования
DAYS_FORECAST_SHORT = int(os.getenv('DAYS_FORECAST_SHORT', 40))
DAYS_FORECAST_LONG = int(os.getenv('DAYS_FORECAST_LONG', 120))
SALES_HISTORY_DAYS = int(os.getenv('SALES_HISTORY_DAYS', 90))

# Настройки API
OZON_API_KEY = os.getenv('OZON_API_KEY')
OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID')

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
    for var in required_vars:
        if not globals().get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {missing_vars}")
        return False
    
    logger.info("Конфигурация загружена успешно")
    return True

def get_moq_for_sku(sku_name: str) -> int:
    """
    Возвращает минимальную партию для закупки по SKU
    """
    return MINIMUM_ORDER_QUANTITIES.get(sku_name, 1000)  # По умолчанию 1000 шт 