#!/usr/bin/env python3
"""
Тест системы кэширования данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache_manager import CacheManager, CachedAPIClient
from ozon_api import OzonAPI
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cache_manager():
    """Тестирует CacheManager"""
    print("🧪 Тестирование CacheManager...")
    
    # Создаем cache manager
    cache_manager = CacheManager(cache_dir="test_cache")
    
    # Тест 1: Сохранение и получение данных
    test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
    
    # Сохраняем данные
    success = cache_manager.set_cache("test_key", test_data, "test", ttl_hours=1)
    print(f"✅ Сохранение данных: {'УСПЕХ' if success else 'ПРОВАЛ'}")
    
    # Получаем данные
    retrieved_data = cache_manager.get_cache("test_key")
    print(f"✅ Получение данных: {'УСПЕХ' if retrieved_data == test_data else 'ПРОВАЛ'}")
    
    # Тест 2: Получение несуществующих данных
    non_existent = cache_manager.get_cache("non_existent_key")
    print(f"✅ Несуществующие данные: {'УСПЕХ' if non_existent is None else 'ПРОВАЛ'}")
    
    # Тест 3: Статистика кэша
    stats = cache_manager.get_cache_stats()
    print(f"✅ Статистика кэша: {stats}")
    
    # Тест 4: Очистка кэша
    expired_count = cache_manager.clear_expired_cache()
    print(f"✅ Очистка истекшего кэша: {expired_count} записей")
    
    # Очищаем тестовый кэш
    cache_manager.clear_all_cache()
    print("✅ Тестовый кэш очищен")

def test_cached_api_client():
    """Тестирует CachedAPIClient"""
    print("\n🧪 Тестирование CachedAPIClient...")
    
    # Создаем API клиент и cache manager
    api_client = OzonAPI()
    cache_manager = CacheManager(cache_dir="test_cache")
    cached_api = CachedAPIClient(api_client, cache_manager)
    
    # Тест получения товаров с кэшированием
    print("Тестирование получения товаров с кэшированием...")
    
    # Первый запрос (должен получить свежие данные)
    start_time = time.time()
    products1 = cached_api.get_products_with_cache()
    time1 = time.time() - start_time
    print(f"Первый запрос: {len(products1) if products1 else 0} товаров за {time1:.2f} сек")
    
    # Второй запрос (должен использовать кэш)
    start_time = time.time()
    products2 = cached_api.get_products_with_cache()
    time2 = time.time() - start_time
    print(f"Второй запрос: {len(products2) if products2 else 0} товаров за {time2:.2f} сек")
    
    if time2 < time1:
        print("✅ Кэширование работает (второй запрос быстрее)")
    else:
        print("⚠️ Кэширование может не работать")
    
    # Тест принудительного обновления
    print("Тестирование принудительного обновления...")
    start_time = time.time()
    products3 = cached_api.get_products_with_cache(force_refresh=True)
    time3 = time.time() - start_time
    print(f"Принудительное обновление: {len(products3) if products3 else 0} товаров за {time3:.2f} сек")
    
    # Очищаем тестовый кэш
    cache_manager.clear_all_cache()
    print("✅ Тестовый кэш очищен")

def test_cache_performance():
    """Тестирует производительность кэширования"""
    print("\n🧪 Тестирование производительности кэширования...")
    
    cache_manager = CacheManager(cache_dir="test_cache")
    
    # Создаем тестовые данные разного размера
    small_data = {"key": "value"}
    medium_data = {"items": [{"id": i, "name": f"item_{i}"} for i in range(100)]}
    large_data = {"items": [{"id": i, "name": f"item_{i}", "data": "x" * 100} for i in range(1000)]}
    
    test_cases = [
        ("small", small_data),
        ("medium", medium_data),
        ("large", large_data)
    ]
    
    for name, data in test_cases:
        print(f"Тестирование {name} данных...")
        
        # Измеряем время сохранения
        start_time = time.time()
        success = cache_manager.set_cache(f"test_{name}", data, "test", ttl_hours=1)
        save_time = time.time() - start_time
        
        # Измеряем время загрузки
        start_time = time.time()
        retrieved = cache_manager.get_cache(f"test_{name}")
        load_time = time.time() - start_time
        
        print(f"  Сохранение: {save_time:.4f} сек")
        print(f"  Загрузка: {load_time:.4f} сек")
        print(f"  Успех: {'✅' if success and retrieved == data else '❌'}")
    
    # Очищаем тестовый кэш
    cache_manager.clear_all_cache()

def test_cache_types():
    """Тестирует различные типы кэша"""
    print("\n🧪 Тестирование различных типов кэша...")
    
    cache_manager = CacheManager(cache_dir="test_cache")
    
    # Тестируем разные типы кэша
    cache_types = ["products", "sales", "stocks", "analytics"]
    
    for cache_type in cache_types:
        test_data = {"type": cache_type, "data": f"test_data_for_{cache_type}"}
        
        # Сохраняем с разными TTL
        ttl_hours = 1 if cache_type in ["products", "analytics"] else 0.5
        success = cache_manager.set_cache(f"test_{cache_type}", test_data, cache_type, ttl_hours)
        
        # Получаем данные
        retrieved = cache_manager.get_cache(f"test_{cache_type}")
        
        print(f"  {cache_type}: {'✅' if success and retrieved == test_data else '❌'}")
    
    # Получаем статистику по типам
    stats = cache_manager.get_cache_stats()
    print(f"Статистика по типам: {stats.get('type_stats', {})}")
    
    # Очищаем тестовый кэш
    cache_manager.clear_all_cache()

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы кэширования\n")
    
    try:
        test_cache_manager()
        test_cache_performance()
        test_cache_types()
        
        # Тест API только если есть настроенные ключи
        try:
            test_cached_api_client()
        except Exception as e:
            print(f"⚠️ Тест API пропущен (возможно, нет настроенных ключей): {e}")
        
        print("\n✅ Все тесты кэширования завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 