#!/usr/bin/env python3
"""
Тест системы валидации данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from forecast import DataValidator, PurchaseForecast
import pandas as pd
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sales_validation():
    """Тестирует валидацию данных о продажах"""
    print("🧪 Тестирование валидации данных о продажах...")
    
    # Тест 1: Корректные данные
    valid_sales = [
        {"sku": "TEST001", "date": "2024-01-01", "quantity": 5, "revenue": 1000},
        {"sku": "TEST002", "date": "2024-01-01", "quantity": 3, "revenue": 600},
    ]
    
    is_valid, errors = DataValidator.validate_sales_data(valid_sales)
    print(f"✅ Корректные данные: {'ПРОЙДЕН' if is_valid else 'ПРОВАЛЕН'}")
    if errors:
        print(f"   Ошибки: {errors}")
    
    # Тест 2: Данные с ошибками
    invalid_sales = [
        {"sku": "TEST001", "date": "2024-01-01", "quantity": -5},  # Отрицательное количество
        {"sku": 123, "date": "2024-01-01", "quantity": 5},  # SKU не строка
        {"sku": "TEST002", "date": "invalid-date", "quantity": 5},  # Некорректная дата
        {"sku": "TEST003", "date": "2024-01-01", "quantity": 2000},  # Подозрительно большое количество
    ]
    
    is_valid, errors = DataValidator.validate_sales_data(invalid_sales)
    print(f"❌ Данные с ошибками: {'ПРОЙДЕН' if not is_valid else 'ПРОВАЛЕН'}")
    print(f"   Найдено ошибок: {len(errors)}")
    for error in errors[:3]:
        print(f"   - {error}")
    
    # Тест 3: Пустые данные
    is_valid, errors = DataValidator.validate_sales_data([])
    print(f"❌ Пустые данные: {'ПРОЙДЕН' if not is_valid else 'ПРОВАЛЕН'}")

def test_stocks_validation():
    """Тестирует валидацию данных об остатках"""
    print("\n🧪 Тестирование валидации данных об остатках...")
    
    # Тест 1: Корректные данные
    valid_stocks = [
        {"sku": "TEST001", "stock": 100, "reserved": 10},
        {"sku": "TEST002", "stock": 50, "reserved": 5},
    ]
    
    is_valid, errors = DataValidator.validate_stocks_data(valid_stocks)
    print(f"✅ Корректные данные: {'ПРОЙДЕН' if is_valid else 'ПРОВАЛЕН'}")
    
    # Тест 2: Данные с ошибками
    invalid_stocks = [
        {"sku": "TEST001", "stock": -10, "reserved": 5},  # Отрицательный остаток
        {"sku": "TEST002", "stock": 50, "reserved": 60},  # Зарезервировано больше общего остатка
        {"sku": 123, "stock": 50, "reserved": 5},  # SKU не строка
    ]
    
    is_valid, errors = DataValidator.validate_stocks_data(invalid_stocks)
    print(f"❌ Данные с ошибками: {'ПРОЙДЕН' if not is_valid else 'ПРОВАЛЕН'}")
    print(f"   Найдено ошибок: {len(errors)}")
    for error in errors:
        print(f"   - {error}")

def test_data_cleaning():
    """Тестирует очистку данных"""
    print("\n🧪 Тестирование очистки данных...")
    
    # Создаем DataFrame с выбросами
    sales_data = [
        {"sku": "TEST001", "date": "2024-01-01", "quantity": 5, "revenue": 1000},
        {"sku": "TEST001", "date": "2024-01-02", "quantity": -3, "revenue": 600},  # Отрицательное количество
        {"sku": "TEST001", "date": "2024-01-03", "quantity": 1000, "revenue": 200000},  # Выброс
        {"sku": "", "date": "2024-01-04", "quantity": 5, "revenue": 1000},  # Пустой SKU
        {"sku": "TEST002", "date": None, "quantity": 5, "revenue": 1000},  # Некорректная дата
    ]
    
    df = pd.DataFrame(sales_data)
    print(f"Исходные данные: {len(df)} записей")
    
    cleaned_df = DataValidator.clean_sales_data(df)
    print(f"После очистки: {len(cleaned_df)} записей")
    print(f"Удалено записей: {len(df) - len(cleaned_df)}")

def test_forecast_with_validation():
    """Тестирует прогнозирование с валидацией"""
    print("\n🧪 Тестирование прогнозирования с валидацией...")
    
    # Создаем тестовые данные
    sales_data = [
        {"sku": "TEST001", "date": "2024-01-01", "quantity": 5, "revenue": 1000},
        {"sku": "TEST001", "date": "2024-01-02", "quantity": 3, "revenue": 600},
        {"sku": "TEST001", "date": "2024-01-03", "quantity": 7, "revenue": 1400},
        {"sku": "TEST002", "date": "2024-01-01", "quantity": 2, "revenue": 400},
        {"sku": "TEST002", "date": "2024-01-02", "quantity": 1, "revenue": 200},
    ]
    
    stocks_data = [
        {"sku": "TEST001", "stock": 50, "reserved": 5},
        {"sku": "TEST002", "stock": 20, "reserved": 2},
        {"sku": "TEST003", "stock": 100, "reserved": 10},  # Нет данных о продажах
    ]
    
    # Создаем экземпляр прогнозирования
    forecast = PurchaseForecast()
    
    # Подготавливаем данные
    sales_df = forecast.prepare_sales_data(sales_data)
    stocks_df = forecast.prepare_stocks_data(stocks_data)
    
    print(f"Подготовлено продаж: {len(sales_df)} записей")
    print(f"Подготовлено остатков: {len(stocks_df)} записей")
    
    # Рассчитываем прогноз
    forecast_result = forecast.calculate_forecast(sales_df, stocks_df)
    
    if not forecast_result.empty:
        print(f"Рассчитан прогноз для {len(forecast_result)} SKU")
        
        # Генерируем отчет
        report = forecast.generate_purchase_report(forecast_result)
        print(f"Сгенерирован отчет для {len(report)} SKU")
        
        # Показываем качество прогноза
        quality_stats = forecast_result['forecast_quality'].value_counts()
        print("Качество прогноза:")
        for quality, count in quality_stats.items():
            print(f"  {quality}: {count} SKU")
    else:
        print("❌ Не удалось рассчитать прогноз")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы валидации данных\n")
    
    try:
        test_sales_validation()
        test_stocks_validation()
        test_data_cleaning()
        test_forecast_with_validation()
        
        print("\n✅ Все тесты завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 