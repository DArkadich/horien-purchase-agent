#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации функциональности модуля прогнозирования
"""

import pandas as pd
from datetime import datetime, timedelta
import random
from forecast import PurchaseForecast, DataValidator

def generate_test_sales_data(num_skus=50, days=30):
    """Генерирует тестовые данные о продажах"""
    sales_data = []
    
    # Генерируем SKU
    skus = [f"SKU_{i:03d}" for i in range(1, num_skus + 1)]
    
    # Генерируем даты
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    for sku in skus:
        # Базовая продажа для каждого SKU
        base_sales = random.randint(1, 20)
        
        for date in dates:
            # Добавляем случайность и сезонность
            daily_sales = max(0, int(base_sales + random.gauss(0, 3)))
            
            # Сезонность: больше продаж в выходные
            if date.weekday() >= 5:  # Суббота и воскресенье
                daily_sales = int(daily_sales * 1.5)
            
            if daily_sales > 0:
                sales_data.append({
                    'sku': sku,
                    'date': date.strftime('%Y-%m-%d'),
                    'quantity': daily_sales,
                    'revenue': daily_sales * random.uniform(100, 1000)
                })
    
    return sales_data

def generate_test_stocks_data(num_skus=50):
    """Генерирует тестовые данные об остатках"""
    stocks_data = []
    
    skus = [f"SKU_{i:03d}" for i in range(1, num_skus + 1)]
    
    for sku in skus:
        stock = random.randint(0, 100)
        reserved = random.randint(0, min(stock, 30))
        
        stocks_data.append({
            'sku': sku,
            'stock': stock,
            'reserved': reserved
        })
    
    return stocks_data

def test_forecast_functionality():
    """Тестирует основную функциональность прогнозирования"""
    print("🧪 Тестирование модуля прогнозирования")
    print("=" * 50)
    
    # Создаем экземпляр класса прогнозирования
    forecast = PurchaseForecast()
    
    # Генерируем тестовые данные
    print("📊 Генерация тестовых данных...")
    sales_data = generate_test_sales_data(num_skus=30, days=60)
    stocks_data = generate_test_stocks_data(num_skus=30)
    
    print(f"   Создано {len(sales_data)} записей о продажах")
    print(f"   Создано {len(stocks_data)} записей об остатках")
    
    # Валидация данных
    print("\n🔍 Валидация данных...")
    sales_valid, sales_errors = DataValidator.validate_sales_data(sales_data)
    stocks_valid, stocks_errors = DataValidator.validate_stocks_data(stocks_data)
    
    print(f"   Продажи: {'✅' if sales_valid else '❌'}")
    if not sales_valid:
        print(f"   Ошибки: {len(sales_errors)}")
    
    print(f"   Остатки: {'✅' if stocks_valid else '❌'}")
    if not stocks_valid:
        print(f"   Ошибки: {len(stocks_errors)}")
    
    # Подготовка данных
    print("\n📈 Подготовка данных...")
    sales_df = forecast.prepare_sales_data(sales_data)
    stocks_df = forecast.prepare_stocks_data(stocks_data)
    
    print(f"   Подготовлено {len(sales_df)} записей о продажах")
    print(f"   Подготовлено {len(stocks_df)} записей об остатках")
    
    # Расчет прогноза
    print("\n🎯 Расчет прогноза...")
    forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
    
    if not forecast_df.empty:
        print(f"   Рассчитан прогноз для {len(forecast_df)} SKU")
        
        # Валидация результатов прогноза
        forecast_valid, forecast_errors = forecast.validate_forecast_data(forecast_df)
        print(f"   Валидация прогноза: {'✅' if forecast_valid else '❌'}")
        if not forecast_valid:
            print(f"   Ошибки: {len(forecast_errors)}")
        
        # Генерация отчета
        print("\n📋 Генерация отчета...")
        report = forecast.generate_purchase_report(forecast_df)
        print(f"   Создан отчет для {len(report)} позиций")
        
        # Аналитика
        print("\n📊 Генерация аналитики...")
        analytics = forecast.get_forecast_analytics(forecast_df)
        if analytics:
            print(f"   Всего SKU: {analytics['total_skus']}")
            print(f"   Требуют закупки: {analytics['skus_needing_purchase']}")
            print(f"   Критических позиций: {analytics['skus_critical']}")
            print(f"   Общее количество: {analytics['total_recommended_quantity']} шт")
        
        # Рекомендации
        print("\n💡 Генерация рекомендаций...")
        recommendations = forecast.get_forecast_recommendations(forecast_df)
        print(f"   Создано {len(recommendations)} рекомендаций")
        
        # Данные для дашборда
        print("\n📈 Генерация данных для дашборда...")
        dashboard_data = forecast.generate_dashboard_data(forecast_df, sales_df)
        print(f"   Создано {len(dashboard_data.get('alerts', []))} алертов")
        
        # Анализ сезонности
        print("\n📅 Анализ сезонности...")
        seasonality = forecast.analyze_seasonality(sales_df)
        if seasonality:
            peak_day = seasonality['peak_day']
            peak_month = seasonality['peak_month']
            print(f"   Пиковый день: {peak_day['day']} ({peak_day['avg_sales']} шт)")
            print(f"   Пиковый месяц: {peak_month['month']} ({peak_month['avg_sales']} шт)")
        
        # Экспорт отчетов
        print("\n💾 Экспорт отчетов...")
        csv_file = forecast.export_report_to_csv(report)
        json_file = forecast.export_report_to_json(report)
        
        if csv_file:
            print(f"   CSV отчет: {csv_file}")
        if json_file:
            print(f"   JSON отчет: {json_file}")
        
        # Создание текстового отчета
        print("\n📄 Создание текстового отчета...")
        summary_report = forecast.create_forecast_summary_report(
            forecast_df, analytics, recommendations
        )
        print("   Текстовый отчет создан")
        
        # Telegram сообщение
        print("\n📱 Генерация Telegram сообщения...")
        telegram_message = forecast.generate_telegram_message(report)
        print(f"   Сообщение длиной {len(telegram_message)} символов")
        
        # Показываем пример отчета
        print("\n📋 Пример отчета:")
        if report:
            example = report[0]
            print(f"   SKU: {example['sku']}")
            print(f"   Средняя продажа: {example['avg_daily_sales']} шт/день")
            print(f"   Текущий остаток: {example['current_stock']} шт")
            print(f"   Дней до исчерпания: {example['days_until_stockout']}")
            print(f"   Рекомендуемое количество: {example['recommended_quantity']} шт")
            print(f"   Качество прогноза: {example['forecast_quality']}")
            print(f"   Уверенность: {example['confidence']}")
            print(f"   Срочность: {example['urgency']}")
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    test_forecast_functionality() 