#!/usr/bin/env python3
"""
Тестовый скрипт для проверки различных эндпоинтов Ozon API
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ozon_api import OzonAPI

def test_ozon_endpoints():
    """Тестирует различные эндпоинты Ozon API"""
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Проверяем наличие API ключей
    api_key = os.getenv('OZON_API_KEY')
    client_id = os.getenv('OZON_CLIENT_ID')
    
    print("🔍 Тестирование Ozon API эндпоинтов...")
    print("=" * 50)
    
    print(f"🔑 API Key: {'✅ Установлен' if api_key and api_key != 'your_ozon_api_key_here' else '❌ Не установлен'}")
    print(f"🔑 Client ID: {'✅ Установлен' if client_id and client_id != 'your_ozon_client_id_here' else '❌ Не установлен'}")
    
    if not api_key or api_key == 'your_ozon_api_key_here':
        print("\n❌ Ошибка: API ключи не настроены!")
        print("Пожалуйста, обновите файл .env с реальными ключами")
        return
    
    # Инициализируем API
    api = OzonAPI()
    
    print("\n📊 Тест 1: Получение списка товаров...")
    products = api.get_products()
    if products:
        print(f"✅ Получено {len(products)} товаров")
        if products:
            print(f"Пример товара: {list(products[0].keys())}")
    else:
        print("❌ Не удалось получить товары")
    
    print("\n📊 Тест 2: Получение данных об остатках...")
    stocks = api.get_stocks_data()
    if stocks:
        print(f"✅ Получено {len(stocks)} записей об остатках")
        if stocks:
            print(f"Пример остатка: {stocks[0]}")
    else:
        print("❌ Не удалось получить остатки")
    
    print("\n📊 Тест 3: Аналитические данные...")
    analytics = api.get_analytics_data(days=7)
    if analytics:
        print(f"✅ Получено {len(analytics)} аналитических записей")
        if analytics:
            print(f"Структура: {list(analytics[0].keys())}")
            print(f"Пример: {analytics[0]}")
    else:
        print("❌ Не удалось получить аналитические данные")
    
    print("\n📊 Тест 4: Создание отчета о товарах...")
    report_id = api.create_products_report()
    if report_id:
        print(f"✅ Отчет создан, ID: {report_id}")
        
        # Проверяем статус отчета
        status = api.get_report_status(report_id)
        if status:
            print(f"Статус отчета: {status.get('status', 'unknown')}")
    else:
        print("❌ Не удалось создать отчет")
    
    print("\n" + "=" * 50)
    print("🏁 Тестирование завершено")

if __name__ == "__main__":
    test_ozon_endpoints() 