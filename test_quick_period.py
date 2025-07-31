#!/usr/bin/env python3
"""
Быстрый тест для проверки работы системы с периодом анализа в 2 дня
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DAYS_TO_ANALYZE
from forecast import PurchaseForecast, DataValidator

def test_2_days_period():
    """Тест работы системы с периодом в 2 дня"""
    print("🧪 Тестирование системы с периодом анализа в 2 дня...")
    
    # Проверяем константу
    print(f"✅ Период анализа: {DAYS_TO_ANALYZE} дней")
    assert DAYS_TO_ANALYZE == 2, f"Ожидалось 2 дня, получено {DAYS_TO_ANALYZE}"
    
    # Тестовые данные за 2 дня
    test_sales_data = [
        {"sku": "SKU_001", "date": "2024-01-01", "quantity": 10, "revenue": 1000},
        {"sku": "SKU_001", "date": "2024-01-02", "quantity": 15, "revenue": 1500},
        {"sku": "SKU_002", "date": "2024-01-01", "quantity": 5, "revenue": 500},
        {"sku": "SKU_002", "date": "2024-01-02", "quantity": 8, "revenue": 800},
    ]
    
    test_stocks_data = [
        {"sku": "SKU_001", "stock": 50, "reserved": 10},
        {"sku": "SKU_002", "stock": 30, "reserved": 5},
    ]
    
    # Валидируем данные
    sales_valid, sales_errors = DataValidator.validate_sales_data(test_sales_data)
    stocks_valid, stocks_errors = DataValidator.validate_stocks_data(test_stocks_data)
    
    print(f"✅ Валидация данных о продажах: {sales_valid}")
    print(f"✅ Валидация данных об остатках: {stocks_valid}")
    
    assert sales_valid, f"Ошибки валидации продаж: {sales_errors}"
    assert stocks_valid, f"Ошибки валидации остатков: {stocks_errors}"
    
    # Создаем прогноз
    forecast = PurchaseForecast()
    
    # Подготавливаем данные
    sales_df = forecast.prepare_sales_data(test_sales_data)
    stocks_df = forecast.prepare_stocks_data(test_stocks_data)
    
    print(f"✅ Подготовлено записей о продажах: {len(sales_df)}")
    print(f"✅ Подготовлено записей об остатках: {len(stocks_df)}")
    
    # Рассчитываем прогноз
    forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
    
    print(f"✅ Рассчитан прогноз для {len(forecast_df)} SKU")
    
    # Проверяем, что система работает с 2 днями
    for _, row in forecast_df.iterrows():
        print(f"  SKU {row['sku']}: {row['total_sales_days']} дней продаж")
        assert row['total_sales_days'] <= 2, f"SKU {row['sku']} имеет больше 2 дней данных"
    
    # Генерируем отчет
    report = forecast.generate_purchase_report(forecast_df)
    print(f"✅ Сгенерирован отчет с {len(report)} позициями")
    
    print("\n🎉 Система успешно работает с периодом анализа в 2 дня!")

if __name__ == "__main__":
    test_2_days_period() 