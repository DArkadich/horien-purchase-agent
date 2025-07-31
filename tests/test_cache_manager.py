"""
Unit-тесты для модуля cache_manager.py
"""

import pytest
import os
import json
import time
from unittest.mock import Mock, patch
from cache_manager import CacheManager, CachedAPIClient

class TestCacheManager:
    """Тесты для CacheManager"""
    
    @pytest.mark.unit
    def test_init(self, test_cache_dir):
        """Тест инициализации CacheManager"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        assert cache_manager.cache_dir == test_cache_dir
        assert os.path.exists(test_cache_dir)
    
    @pytest.mark.unit
    def test_set_cache(self, test_cache_dir):
        """Тест сохранения данных в кэш"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        test_data = {"test": "data", "number": 42}
        success = cache_manager.set_cache("test_key", test_data, "test_type", ttl_hours=1)
        
        assert success is True
        
        # Проверяем, что файл создан
        cache_file = os.path.join(test_cache_dir, "test_key.json")
        assert os.path.exists(cache_file)
    
    @pytest.mark.unit
    def test_get_cache(self, test_cache_dir):
        """Тест получения данных из кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Сохраняем данные
        test_data = {"test": "data", "number": 42}
        cache_manager.set_cache("test_key", test_data, "test_type", ttl_hours=1)
        
        # Получаем данные
        retrieved_data = cache_manager.get_cache("test_key")
        
        assert retrieved_data == test_data
    
    @pytest.mark.unit
    def test_get_cache_nonexistent(self, test_cache_dir):
        """Тест получения несуществующих данных"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        result = cache_manager.get_cache("nonexistent_key")
        assert result is None
    
    @pytest.mark.unit
    def test_get_cache_expired(self, test_cache_dir):
        """Тест получения истекших данных"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Сохраняем данные с коротким TTL
        test_data = {"test": "data"}
        cache_manager.set_cache("test_key", test_data, "test_type", ttl_hours=0.001)
        
        # Ждем истечения TTL
        time.sleep(0.1)
        
        # Пытаемся получить данные
        result = cache_manager.get_cache("test_key")
        assert result is None
    
    @pytest.mark.unit
    def test_clear_expired_cache(self, test_cache_dir):
        """Тест очистки истекшего кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Сохраняем данные с разными TTL
        cache_manager.set_cache("expired_key", {"data": "expired"}, "test", ttl_hours=0.001)
        cache_manager.set_cache("valid_key", {"data": "valid"}, "test", ttl_hours=1)
        
        # Ждем истечения первого TTL
        time.sleep(0.1)
        
        # Очищаем истекший кэш
        expired_count = cache_manager.clear_expired_cache()
        
        assert expired_count >= 1
        
        # Проверяем, что истекшие данные удалены
        assert cache_manager.get_cache("expired_key") is None
        assert cache_manager.get_cache("valid_key") is not None
    
    @pytest.mark.unit
    def test_clear_all_cache(self, test_cache_dir):
        """Тест очистки всего кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Сохраняем несколько записей
        cache_manager.set_cache("key1", {"data": "1"}, "test", ttl_hours=1)
        cache_manager.set_cache("key2", {"data": "2"}, "test", ttl_hours=1)
        
        # Очищаем весь кэш
        cache_manager.clear_all_cache()
        
        # Проверяем, что все данные удалены
        assert cache_manager.get_cache("key1") is None
        assert cache_manager.get_cache("key2") is None
    
    @pytest.mark.unit
    def test_get_cache_stats(self, test_cache_dir):
        """Тест получения статистики кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Сохраняем данные разных типов
        cache_manager.set_cache("key1", {"data": "1"}, "products", ttl_hours=1)
        cache_manager.set_cache("key2", {"data": "2"}, "sales", ttl_hours=1)
        cache_manager.set_cache("key3", {"data": "3"}, "stocks", ttl_hours=1)
        
        # Получаем статистику
        stats = cache_manager.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert 'total_entries' in stats
        assert 'expired_entries' in stats
        assert 'type_stats' in stats
        
        # Проверяем количество записей
        assert stats['total_entries'] >= 3
    
    @pytest.mark.unit
    def test_cache_with_different_types(self, test_cache_dir):
        """Тест кэширования разных типов данных"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Тестируем разные типы данных
        test_cases = [
            ("string", "test_string", "string_type"),
            ("number", 42, "number_type"),
            ("list", [1, 2, 3], "list_type"),
            ("dict", {"key": "value"}, "dict_type"),
            ("nested", {"list": [1, 2], "dict": {"nested": "value"}}, "nested_type")
        ]
        
        for key, data, cache_type in test_cases:
            success = cache_manager.set_cache(key, data, cache_type, ttl_hours=1)
            assert success is True
            
            retrieved = cache_manager.get_cache(key)
            assert retrieved == data
    
    @pytest.mark.unit
    def test_cache_ttl_validation(self, test_cache_dir):
        """Тест валидации TTL"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        
        # Тестируем отрицательный TTL
        success = cache_manager.set_cache("test_key", {"data": "test"}, "test", ttl_hours=-1)
        assert success is False
        
        # Тестируем нулевой TTL
        success = cache_manager.set_cache("test_key", {"data": "test"}, "test", ttl_hours=0)
        assert success is False

class TestCachedAPIClient:
    """Тесты для CachedAPIClient"""
    
    @pytest.mark.unit
    def test_init(self, mock_ozon_api, test_cache_dir):
        """Тест инициализации CachedAPIClient"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        assert cached_api.api_client == mock_ozon_api
        assert cached_api.cache_manager == cache_manager
    
    @pytest.mark.unit
    def test_get_products_with_cache(self, mock_ozon_api, test_cache_dir):
        """Тест получения товаров с кэшированием"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Первый запрос - должен получить данные из API
        products1 = cached_api.get_products_with_cache()
        assert products1 is not None
        assert len(products1) > 0
        
        # Второй запрос - должен использовать кэш
        products2 = cached_api.get_products_with_cache()
        assert products2 == products1
    
    @pytest.mark.unit
    def test_get_products_with_cache_force_refresh(self, mock_ozon_api, test_cache_dir):
        """Тест принудительного обновления кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Первый запрос
        products1 = cached_api.get_products_with_cache()
        
        # Принудительное обновление
        products2 = cached_api.get_products_with_cache(force_refresh=True)
        
        assert products2 is not None
        assert len(products2) > 0
    
    @pytest.mark.unit
    def test_get_sales_data_with_cache(self, mock_ozon_api, test_cache_dir):
        """Тест получения данных о продажах с кэшированием"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Получаем данные о продажах
        sales_data = cached_api.get_sales_data_with_cache(days=30)
        
        assert sales_data is not None
        assert len(sales_data) > 0
        
        # Проверяем структуру данных
        for record in sales_data:
            assert 'sku' in record
            assert 'date' in record
            assert 'quantity' in record
    
    @pytest.mark.unit
    def test_get_stocks_data_with_cache(self, mock_ozon_api, test_cache_dir):
        """Тест получения данных об остатках с кэшированием"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Получаем данные об остатках
        stocks_data = cached_api.get_stocks_data_with_cache()
        
        assert stocks_data is not None
        assert len(stocks_data) > 0
        
        # Проверяем структуру данных
        for record in stocks_data:
            assert 'sku' in record
            assert 'stock' in record
            assert 'reserved' in record
    
    @pytest.mark.unit
    def test_cache_key_generation(self, mock_ozon_api, test_cache_dir):
        """Тест генерации ключей кэша"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Проверяем, что ключи генерируются корректно
        products_key = cached_api._get_cache_key("products")
        sales_key = cached_api._get_cache_key("sales", days=30)
        stocks_key = cached_api._get_cache_key("stocks")
        
        assert "products" in products_key
        assert "sales" in sales_key
        assert "stocks" in stocks_key
        assert "30" in sales_key  # Параметр days должен быть в ключе
    
    @pytest.mark.unit
    def test_cache_disabled(self, mock_ozon_api, test_cache_dir):
        """Тест работы с отключенным кэшем"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        cached_api = CachedAPIClient(mock_ozon_api, cache_manager)
        
        # Отключаем кэширование
        cached_api.cache_enabled = False
        
        # Получаем данные
        products = cached_api.get_products_with_cache()
        
        assert products is not None
        assert len(products) > 0
        
        # Проверяем, что данные не кэшируются
        cache_stats = cache_manager.get_cache_stats()
        assert cache_stats['total_entries'] == 0 