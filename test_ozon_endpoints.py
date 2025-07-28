#!/usr/bin/env python3
"""
Тест эндпоинтов Ozon API
"""

import os
import requests
import json
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def test_ozon_api():
    """Тестирует различные эндпоинты Ozon API"""
    
    print("==================================================")
    print("ТЕСТ ЭНДПОИНТОВ OZON API")
    print("==================================================")
    
    # Получаем API ключи
    api_key = os.getenv('OZON_API_KEY')
    client_id = os.getenv('OZON_CLIENT_ID')
    
    if not api_key or not client_id:
        print("❌ API ключи не настроены!")
        print("Добавьте в .env файл:")
        print("OZON_API_KEY=ваш_api_ключ")
        print("OZON_CLIENT_ID=ваш_client_id")
        return
    
    print(f"✅ API ключи настроены")
    print(f"Client ID: {client_id[:8]}...")
    print(f"API Key: {api_key[:8]}...")
    print()
    
    # Настройки запроса
    base_url = "https://api-seller.ozon.ru"
    headers = {
        "Client-Id": client_id,
        "Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Тестируем различные эндпоинты
    endpoints_to_test = [
        {
            "name": "Список товаров (v3)",
            "endpoint": "/v3/product/list",
            "data": {
                "limit": 10,
                "offset": 0,
                "filter": {
                    "visibility_details": {
                        "active": True
                    }
                },
                "with": {
                    "price": True,
                    "stock": True
                }
            }
        },
        {
            "name": "Список товаров (v2)",
            "endpoint": "/v2/product/list",
            "data": {
                "limit": 10,
                "offset": 0,
                "with": {
                    "price": True,
                    "stock": True
                }
            }
        },
        {
            "name": "Информация о товарах (v3)",
            "endpoint": "/v3/product/info/list",
            "data": {
                "product_id": [1, 2, 3]
            }
        },
        {
            "name": "Остатки товаров (v3)",
            "endpoint": "/v3/product/info/stocks",
            "data": {
                "product_id": 1
            }
        },
        {
            "name": "Остатки товаров (v2)",
            "endpoint": "/v2/product/info/stocks",
            "data": {
                "product_id": 1
            }
        },
        {
            "name": "Аналитика (v1)",
            "endpoint": "/v1/analytics/data",
            "data": {
                "date_from": "2024-10-01",
                "date_to": "2024-10-31",
                "metrics": ["revenue", "orders"],
                "dimension": ["day"],
                "filters": [],
                "sort": [{"key": "day", "order": "ASC"}],
                "limit": 10,
                "offset": 0
            }
        }
    ]
    
    for test in endpoints_to_test:
        print(f"🧪 Тестирование: {test['name']}")
        print(f"   Эндпоинт: {test['endpoint']}")
        
        try:
            url = f"{base_url}{test['endpoint']}"
            response = requests.post(url, headers=headers, json=test['data'])
            
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Успешно!")
                if "result" in result:
                    print(f"   Данные: {len(result['result'])} элементов")
                else:
                    print(f"   Ответ: {result}")
            elif response.status_code == 404:
                print(f"   ❌ Эндпоинт не найден (404)")
                print(f"   Ответ: {response.text[:200]}...")
            elif response.status_code == 401:
                print(f"   ❌ Ошибка аутентификации (401)")
                print(f"   Проверьте API ключи")
            elif response.status_code == 403:
                print(f"   ❌ Ошибка доступа (403)")
                print(f"   Проверьте права доступа")
            else:
                print(f"   ❌ Ошибка {response.status_code}")
                print(f"   Ответ: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")
        
        print()
    
    print("==================================================")
    print("ТЕСТ ЗАВЕРШЕН")
    print("==================================================")

if __name__ == "__main__":
    test_ozon_api() 