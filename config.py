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
DAYS_FORECAST_LONG = int(os.getenv('DAYS_FORECAST_LONG', 30))
# Настройки анализа продаж
SALES_HISTORY_DAYS = int(os.getenv('SALES_HISTORY_DAYS', 180))

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