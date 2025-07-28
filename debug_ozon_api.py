#!/usr/bin/env python3
"""
Детальный тест Ozon API - показывает что возвращает каждый эндпоинт
"""

import os
import requests
import json
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def debug_ozon_api():
    """Детально тестирует каждый эндпоинт Ozon API"""
    
    print("==================================================")
    print("ДЕТАЛЬНЫЙ ТЕСТ OZON API")
    print("==================================================")
    
    # Получаем API ключи
    api_key = os.getenv('OZON_API_KEY')
    client_id = os.getenv('OZON_CLIENT_ID')
    
    if not api_key or not client_id:
        print("❌ API ключи не настроены!")
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
            "name": "Информация о товарах (v3)",
            "endpoint": "/v3/product/info/list",
            "data": {
                "product_id": [1, 2, 3]
            }
        },
        {
            "name": "Заказы (v2)",
            "endpoint": "/v2/order/list",
            "data": {
                "limit": 10,
                "offset": 0,
                "since": "2024-01-01T00:00:00Z",
                "to": "2024-12-31T23:59:59Z",
                "status": "delivered"
            }
        },
        {
            "name": "Заказы (v3)",
            "endpoint": "/v3/order/list",
            "data": {
                "limit": 10,
                "offset": 0,
                "since": "2024-01-01T00:00:00Z",
                "to": "2024-12-31T23:59:59Z",
                "status": "delivered"
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
        },
        {
            "name": "Заказы (v1)",
            "endpoint": "/v1/order/list",
            "data": {
                "limit": 10,
                "offset": 0,
                "since": "2024-01-01T00:00:00Z",
                "to": "2024-12-31T23:59:59Z",
                "status": "delivered"
            }
        },
        {
            "name": "Остатки FBO",
            "endpoint": "/v1/product/info/stocks",
            "data": {
                "product_id": 2119951820
            }
        },
        {
            "name": "Остатки FBS",
            "endpoint": "/v2/product/info/stocks",
            "data": {
                "product_id": 2119951820
            }
        },
        {
            "name": "Информация о товаре с остатками",
            "endpoint": "/v3/product/info/list",
            "data": {
                "product_id": [2119951820, 2119951824, 2119951828]
            }
        },
        {
            "name": "Отчёт об остатках (v1)",
            "endpoint": "/v1/report/list",
            "data": {
                "report_type": "SELLER_STOCK",
                "page_size": 100,
                "page": 1
            }
        },
        {
            "name": "Заказы (v1) - альтернативный",
            "endpoint": "/v1/order/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Заказы (v2) - альтернативный",
            "endpoint": "/v2/order/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Отчёт о заказах",
            "endpoint": "/v1/report/list",
            "data": {
                "report_type": "SELLER_ORDERS",
                "page_size": 100,
                "page": 1
            }
        },
        {
            "name": "Отчёт о товарах компании",
            "endpoint": "/v1/report/create",
            "data": {
                "report_type": "COMPANY_POSTINGS",
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }
        },
        {
            "name": "Заказы (v3) - альтернативный",
            "endpoint": "/v3/order/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Заказы (v4)",
            "endpoint": "/v4/order/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Заказы (v5)",
            "endpoint": "/v5/order/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Продажи (v1)",
            "endpoint": "/v1/sales/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Продажи (v2)",
            "endpoint": "/v2/sales/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Продажи (v3)",
            "endpoint": "/v3/sales/list",
            "data": {
                "limit": 10,
                "offset": 0
            }
        },
        {
            "name": "Аналитика продаж",
            "endpoint": "/v1/analytics/sales",
            "data": {
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }
        },
        {
            "name": "Отчёт о продажах",
            "endpoint": "/v1/report/list",
            "data": {
                "report_type": "SELLER_SALES",
                "page_size": 100,
                "page": 1
            }
        },
        {
            "name": "Выкуп товаров (финансы)",
            "endpoint": "/v1/finance/products/buyout",
            "data": {
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }
        }
    ]
    
    for test in endpoints_to_test:
        print(f"🧪 Тестирование: {test['name']}")
        print(f"   Эндпоинт: {test['endpoint']}")
        print(f"   Данные запроса: {json.dumps(test['data'], indent=2, ensure_ascii=False)}")
        
        try:
            url = f"{base_url}{test['endpoint']}"
            response = requests.post(url, headers=headers, json=test['data'])
            
            print(f"   Статус: {response.status_code}")
            print(f"   Заголовки ответа: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Успешно!")
                print(f"   Структура ответа:")
                print(f"   {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                # Анализируем структуру
                if "result" in result:
                    print(f"   📊 Результат содержит: {list(result['result'].keys()) if isinstance(result['result'], dict) else type(result['result'])}")
                if "items" in result:
                    print(f"   📦 Элементов: {len(result['items'])}")
                if "orders" in result:
                    print(f"   📋 Заказов: {len(result['orders'])}")
                    
            elif response.status_code == 404:
                print(f"   ❌ Эндпоинт не найден (404)")
                print(f"   Ответ: {response.text}")
            elif response.status_code == 400:
                print(f"   ❌ Ошибка валидации (400)")
                print(f"   Ответ: {response.text}")
            elif response.status_code == 401:
                print(f"   ❌ Ошибка аутентификации (401)")
                print(f"   Ответ: {response.text}")
            elif response.status_code == 403:
                print(f"   ❌ Ошибка доступа (403)")
                print(f"   Ответ: {response.text}")
            else:
                print(f"   ❌ Ошибка {response.status_code}")
                print(f"   Ответ: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")
        
        print()
        print("-" * 80)
        print()
    
    print("==================================================")
    print("ТЕСТ ЗАВЕРШЕН")
    print("==================================================")

if __name__ == "__main__":
    debug_ozon_api() 