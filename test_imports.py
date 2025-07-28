#!/usr/bin/env python3
"""
Тестовый скрипт для проверки импортов и базовой функциональности
"""

import sys
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_imports():
    """Тестирует импорт всех модулей"""
    try:
        logger.info("Тестирование импортов...")
    
        # Тестируем импорт конфигурации
        from config import validate_config, logger as config_logger
        logger.info("✓ Конфигурация импортирована")
        
        # Тестируем импорт Ozon API
        from ozon_api import OzonAPI
        logger.info("✓ Ozon API импортирован")
        
        # Тестируем импорт прогнозирования
        from forecast import PurchaseForecast
        logger.info("✓ Модуль прогнозирования импортирован")
        
        # Тестируем импорт Google Sheets
        from sheets import GoogleSheets
        logger.info("✓ Google Sheets импортирован")
        
        # Тестируем импорт Telegram
        from telegram_notify import TelegramNotifier
        logger.info("✓ Telegram уведомления импортированы")
        
        logger.info("✓ Все модули успешно импортированы")
        return True
        
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return False

def test_basic_functionality():
    """Тестирует базовую функциональность"""
    try:
        logger.info("Тестирование базовой функциональности...")
        
        # Тестируем создание объектов
        from ozon_api import OzonAPI
        from forecast import PurchaseForecast
        
        ozon_api = OzonAPI()
        logger.info("✓ OzonAPI объект создан")
        
        forecast = PurchaseForecast()
        logger.info("✓ PurchaseForecast объект создан")
        
        # Тестируем генерацию тестовых данных
        test_products = ozon_api._generate_test_products()
        logger.info(f"✓ Сгенерировано {len(test_products)} тестовых товаров")
        
        test_sales = ozon_api._generate_test_sales_data(30)
        logger.info(f"✓ Сгенерировано {len(test_sales)} тестовых продаж")
        
        test_stocks = ozon_api._generate_test_stocks_data()
        logger.info(f"✓ Сгенерировано {len(test_stocks)} тестовых остатков")
        
        # Тестируем подготовку данных
        sales_df = forecast.prepare_sales_data(test_sales)
        stocks_df = forecast.prepare_stocks_data(test_stocks)
        
        logger.info(f"✓ Подготовлено {len(sales_df)} записей продаж")
        logger.info(f"✓ Подготовлено {len(stocks_df)} записей остатков")
        
        # Тестируем расчет прогноза
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        logger.info(f"✓ Рассчитан прогноз для {len(forecast_df)} SKU")
        
        # Тестируем генерацию отчета
        report = forecast.generate_purchase_report(forecast_df)
        logger.info(f"✓ Сгенерирован отчет для {len(report)} позиций")
        
        logger.info("✓ Базовая функциональность работает корректно")
            return True
            
    except Exception as e:
        logger.error(f"Ошибка тестирования функциональности: {e}")
        return False

def main():
    """Главная функция тестирования"""
    logger.info("=" * 50)
    logger.info("Запуск тестирования системы")
    logger.info("=" * 50)
    
    # Тестируем импорты
    if not test_imports():
        logger.error("Тест импортов не прошел")
        return 1
    
    # Тестируем базовую функциональность
    if not test_basic_functionality():
        logger.error("Тест функциональности не прошел")
        return 1
    
    logger.info("=" * 50)
    logger.info("Все тесты прошли успешно!")
    logger.info("=" * 50)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code) 