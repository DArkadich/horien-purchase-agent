"""
Unit-тесты для модуля config.py
"""

import pytest
import os
from unittest.mock import patch
from config import validate_config, get_moq_for_sku, MINIMUM_ORDER_QUANTITIES

class TestConfig:
    """Тесты для конфигурации"""
    
    @pytest.mark.unit
    def test_validate_config_success(self, patch_env_vars):
        """Тест успешной валидации конфигурации"""
        result = validate_config()
        assert result is True
    
    @pytest.mark.unit
    def test_validate_config_missing_vars(self):
        """Тест валидации с отсутствующими переменными"""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_config()
            assert result is False
    
    @pytest.mark.unit
    def test_validate_config_placeholder_values(self):
        """Тест валидации с placeholder значениями"""
        with patch.dict(os.environ, {
            'OZON_API_KEY': 'your_api_key_here',
            'OZON_CLIENT_ID': 'your_client_id_here',
            'GOOGLE_SERVICE_ACCOUNT_JSON': 'your_service_account.json',
            'GOOGLE_SPREADSHEET_ID': 'your_spreadsheet_id',
            'TELEGRAM_TOKEN': 'your_telegram_token',
            'TELEGRAM_CHAT_ID': 'your_chat_id'
        }):
            result = validate_config()
            assert result is False
    
    @pytest.mark.unit
    def test_get_moq_for_sku_exact_match(self):
        """Тест получения MOQ для точного совпадения SKU"""
        # Тестируем конкретные SKU из конфигурации
        assert get_moq_for_sku("360360") == 24
        assert get_moq_for_sku("500500") == 24
        assert get_moq_for_sku("120120") == 48
    
    @pytest.mark.unit
    def test_get_moq_for_sku_pattern_matching(self):
        """Тест получения MOQ по паттернам SKU"""
        # Однодневные линзы (6 цифр, начинаются на 30)
        assert get_moq_for_sku("301234") == 1
        assert get_moq_for_sku("309999") == 1
        
        # Месячные линзы по 6 шт (5 цифр, начинаются на 6)
        assert get_moq_for_sku("61234") == 1
        assert get_moq_for_sku("69999") == 1
        
        # Месячные линзы по 3 шт (5 цифр, начинаются на 3)
        assert get_moq_for_sku("31234") == 1
        assert get_moq_for_sku("39999") == 1
    
    @pytest.mark.unit
    def test_get_moq_for_sku_default(self):
        """Тест получения MOQ по умолчанию для неизвестных SKU"""
        # Неизвестные SKU должны возвращать значение по умолчанию
        assert get_moq_for_sku("UNKNOWN_SKU") == 5
        assert get_moq_for_sku("12345") == 5  # Не подходит под паттерны
        assert get_moq_for_sku("ABCDEF") == 5  # Не подходит под паттерны
    
    @pytest.mark.unit
    def test_minimum_order_quantities_structure(self):
        """Тест структуры MINIMUM_ORDER_QUANTITIES"""
        # Проверяем, что это словарь
        assert isinstance(MINIMUM_ORDER_QUANTITIES, dict)
        
        # Проверяем, что все значения положительные
        for sku, moq in MINIMUM_ORDER_QUANTITIES.items():
            assert isinstance(sku, str)
            assert isinstance(moq, int)
            assert moq > 0
    
    @pytest.mark.unit
    def test_get_moq_for_sku_edge_cases(self):
        """Тест граничных случаев для get_moq_for_sku"""
        # Пустая строка
        assert get_moq_for_sku("") == 5
        
        # Очень длинная строка
        long_sku = "A" * 100
        assert get_moq_for_sku(long_sku) == 5
        
        # Специальные символы
        assert get_moq_for_sku("SKU-001") == 5
        assert get_moq_for_sku("SKU_001") == 5
        assert get_moq_for_sku("SKU.001") == 5 