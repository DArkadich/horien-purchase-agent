#!/usr/bin/env python3
"""
Тестовый скрипт для проверки аналитического API Ozon
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ozon_api import OzonAPI

def test_analytics_api():
    """Тестирует аналитический API Ozon"""
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Инициализируем API
    api = OzonAPI()
    
    print("🔍 Тестирование аналитического API Ozon...")
    print("=" * 50)
    
    # Тестируем получение аналитических данных за последние 30 дней
    print("📊 Получение аналитических данных за 30 дней...")
    analytics_data = api.get_analytics_data(days=30)
    
    if analytics_data:
        print(f"✅ Получено {len(analytics_data)} записей аналитических данных")
        
        # Показываем первые 3 записи
        print("\n📋 Примеры данных:")
        for i, record in enumerate(analytics_data[:3]):
            print(f"Запись {i+1}:")
            print(json.dumps(record, indent=2, ensure_ascii=False))
            print()
        
        # Анализируем структуру данных
        if analytics_data:
            first_record = analytics_data[0]
            print("🔍 Структура данных:")
            print(f"Ключи: {list(first_record.keys())}")
            
            # Проверяем наличие метрик
            metrics = ["revenue", "orders", "views"]
            for metric in metrics:
                if metric in first_record:
                    print(f"✅ Метрика '{metric}' найдена")
                else:
                    print(f"❌ Метрика '{metric}' отсутствует")
            
            # Проверяем размерности
            dimensions = ["day", "sku"]
            for dimension in dimensions:
                if dimension in first_record:
                    print(f"✅ Размерность '{dimension}' найдена")
                else:
                    print(f"❌ Размерность '{dimension}' отсутствует")
    else:
        print("❌ Не удалось получить аналитические данные")
    
    print("\n" + "=" * 50)
    print("🏁 Тестирование завершено")

if __name__ == "__main__":
    test_analytics_api() 