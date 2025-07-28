#!/usr/bin/env python3
"""
Тестовый скрипт для локального запуска системы
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_stock_tracker():
    """Тестируем систему отслеживания остатков"""
    logger.info("Тестирование системы отслеживания остатков...")
    
    try:
        from stock_tracker import StockTracker
        
        # Инициализируем трекер
        tracker = StockTracker()
        logger.info("✅ StockTracker инициализирован успешно")
        
        # Создаем тестовые данные об остатках
        test_stocks = [
            {"sku": "линза -3.5", "stock": 100, "reserved": 10},
            {"sku": "линза -3.0", "stock": 150, "reserved": 15},
            {"sku": "линза -2.5", "stock": 80, "reserved": 5},
        ]
        
        # Сохраняем тестовые данные
        tracker.save_stock_data(test_stocks)
        logger.info("✅ Тестовые данные об остатках сохранены")
        
        # Получаем историю
        history = tracker.get_stock_history("линза -3.5", days=30)
        logger.info(f"✅ Получена история для линза -3.5: {len(history)} записей")
        
        # Оцениваем продажи
        sales = tracker.estimate_sales_from_stock_changes(days=30)
        logger.info(f"✅ Оценено продаж: {len(sales)} записей")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тестировании StockTracker: {e}")
        return False

def test_forecast():
    """Тестируем систему прогнозирования"""
    logger.info("Тестирование системы прогнозирования...")
    
    try:
        from forecast import PurchaseForecast
        
        # Инициализируем прогнозирование
        calculator = PurchaseForecast()
        logger.info("✅ PurchaseForecast инициализирован успешно")
        
        # Создаем тестовые данные
        test_sales = [
            {"sku": "линза -3.5", "quantity": 10, "revenue": 1000, "date": "2024-01-01"},
            {"sku": "линза -3.0", "quantity": 15, "revenue": 1500, "date": "2024-01-01"},
        ]
        
        test_stocks = [
            {"sku": "линза -3.5", "stock": 100, "reserved": 10},
            {"sku": "линза -3.0", "stock": 150, "reserved": 15},
        ]
        
        # Подготавливаем данные
        sales_df = calculator.prepare_sales_data(test_sales)
        stocks_df = calculator.prepare_stocks_data(test_stocks)
        
        logger.info(f"✅ Подготовлены данные: продажи {len(sales_df)}, остатки {len(stocks_df)}")
        
        # Рассчитываем прогноз
        forecast = calculator.calculate_forecast(sales_df, stocks_df)
        logger.info(f"✅ Рассчитан прогноз: {len(forecast)} позиций")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тестировании PurchaseForecast: {e}")
        return False

def main():
    """Основная функция тестирования"""
    logger.info("🚀 Запуск локального тестирования системы...")
    
    # Тестируем компоненты
    stock_test = test_stock_tracker()
    forecast_test = test_forecast()
    
    if stock_test and forecast_test:
        logger.info("✅ Все тесты прошли успешно!")
        logger.info("🎯 Система готова к работе с реальными данными")
    else:
        logger.error("❌ Некоторые тесты не прошли")
        sys.exit(1)

if __name__ == "__main__":
    main() 