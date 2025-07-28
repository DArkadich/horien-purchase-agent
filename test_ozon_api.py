#!/usr/bin/env python3
"""
Тест Ozon API для проверки реальных данных
"""

import logging
from ozon_api import OzonAPI
from config import OZON_API_KEY, OZON_CLIENT_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ozon_api():
    """Тестирует Ozon API с реальными данными"""
    
    print("=" * 50)
    print("ТЕСТ OZON API")
    print("=" * 50)
    
    # Проверяем наличие API ключей
    if not OZON_API_KEY or OZON_API_KEY == "your_ozon_api_key_here":
        print("❌ OZON_API_KEY не настроен")
        print("Настройте API ключ в .env файле")
        return False
    
    if not OZON_CLIENT_ID or OZON_CLIENT_ID == "your_ozon_client_id_here":
        print("❌ OZON_CLIENT_ID не настроен")
        print("Настройте Client ID в .env файле")
        return False
    
    print("✅ API ключи настроены")
    
    try:
        # Создаем экземпляр API
        ozon_api = OzonAPI()
        print("✅ OzonAPI объект создан")
        
        # Тестируем получение товаров
        print("\n📦 Тестирование получения товаров...")
        products = ozon_api.get_products()
        
        if products and len(products) > 0:
            print(f"✅ Получено {len(products)} товаров")
            print("Примеры товаров:")
            for i, product in enumerate(products[:3], 1):
                print(f"  {i}. {product.get('name', 'N/A')} (ID: {product.get('id', 'N/A')})")
        else:
            print("⚠️ Товары не получены, используются тестовые данные")
        
        # Тестируем получение продаж
        print("\n📈 Тестирование получения продаж...")
        sales = ozon_api.get_sales_data(days=30)
        
        if sales and len(sales) > 0:
            print(f"✅ Получено {len(sales)} записей о продажах")
            print("Примеры продаж:")
            for i, sale in enumerate(sales[:3], 1):
                print(f"  {i}. {sale.get('sku', 'N/A')} - {sale.get('quantity', 0)} шт")
        else:
            print("⚠️ Продажи не получены, используются тестовые данные")
        
        # Тестируем получение остатков
        print("\n📊 Тестирование получения остатков...")
        stocks = ozon_api.get_stocks_data()
        
        if stocks and len(stocks) > 0:
            print(f"✅ Получено {len(stocks)} записей об остатках")
            print("Примеры остатков:")
            for i, stock in enumerate(stocks[:3], 1):
                print(f"  {i}. {stock.get('sku', 'N/A')} - {stock.get('stock', 0)} шт")
        else:
            print("⚠️ Остатки не получены, используются тестовые данные")
        
        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТ ТЕСТА:")
        
        # Определяем, используются ли реальные данные
        real_data_used = (
            len(products) > 0 and 
            len(sales) > 0 and 
            len(stocks) > 0 and
            not any("тестовые данные" in str(product) for product in products)
        )
        
        if real_data_used:
            print("🎉 РЕАЛЬНЫЕ ДАННЫЕ OZON API РАБОТАЮТ!")
            print("✅ Система готова к работе с реальными данными")
        else:
            print("⚠️ Используются тестовые данные")
            print("🔧 Настройте API ключи для работы с реальными данными")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования Ozon API: {e}")
        return False

if __name__ == "__main__":
    test_ozon_api() 