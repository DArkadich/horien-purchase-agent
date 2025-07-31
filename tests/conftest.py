"""
Конфигурация pytest с общими фикстурами
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pandas as pd

# Добавляем корневую директорию в путь для импорта модулей
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def temp_dir():
    """Создает временную директорию для тестов"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_cache_dir(temp_dir):
    """Создает временную директорию для кэша"""
    cache_dir = os.path.join(temp_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

@pytest.fixture
def test_data_dir(temp_dir):
    """Создает временную директорию для тестовых данных"""
    data_dir = os.path.join(temp_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

@pytest.fixture
def mock_ozon_api():
    """Создает мок для OzonAPI"""
    mock_api = Mock()
    
    # Мок для get_products
    mock_api.get_products.return_value = [
        {"sku": "SKU_001", "name": "Test Product 1", "price": 100},
        {"sku": "SKU_002", "name": "Test Product 2", "price": 200},
        {"sku": "SKU_003", "name": "Test Product 3", "price": 300}
    ]
    
    # Мок для get_sales_data
    mock_api.get_sales_data.return_value = [
        {"sku": "SKU_001", "date": "2024-01-01", "quantity": 10, "revenue": 1000},
        {"sku": "SKU_001", "date": "2024-01-02", "quantity": 15, "revenue": 1500},
        {"sku": "SKU_002", "date": "2024-01-01", "quantity": 5, "revenue": 1000},
        {"sku": "SKU_002", "date": "2024-01-02", "quantity": 8, "revenue": 1600}
    ]
    
    # Мок для get_stocks_data
    mock_api.get_stocks_data.return_value = [
        {"sku": "SKU_001", "stock": 50, "reserved": 10},
        {"sku": "SKU_002", "stock": 30, "reserved": 5},
        {"sku": "SKU_003", "stock": 20, "reserved": 2}
    ]
    
    return mock_api

@pytest.fixture
def sample_sales_data():
    """Создает тестовые данные о продажах"""
    return [
        {"sku": "SKU_001", "date": "2024-01-01", "quantity": 10, "revenue": 1000},
        {"sku": "SKU_001", "date": "2024-01-02", "quantity": 15, "revenue": 1500},
        {"sku": "SKU_001", "date": "2024-01-03", "quantity": 12, "revenue": 1200},
        {"sku": "SKU_002", "date": "2024-01-01", "quantity": 5, "revenue": 1000},
        {"sku": "SKU_002", "date": "2024-01-02", "quantity": 8, "revenue": 1600},
        {"sku": "SKU_002", "date": "2024-01-03", "quantity": 6, "revenue": 1200}
    ]

@pytest.fixture
def sample_stocks_data():
    """Создает тестовые данные об остатках"""
    return [
        {"sku": "SKU_001", "stock": 50, "reserved": 10},
        {"sku": "SKU_002", "stock": 30, "reserved": 5},
        {"sku": "SKU_003", "stock": 20, "reserved": 2}
    ]

@pytest.fixture
def mock_telegram():
    """Создает мок для TelegramNotifier"""
    mock_telegram = Mock()
    mock_telegram.send_message.return_value = True
    mock_telegram.send_purchase_report.return_value = True
    return mock_telegram

@pytest.fixture
def mock_sheets():
    """Создает мок для GoogleSheets"""
    mock_sheets = Mock()
    mock_sheets.write_purchase_report.return_value = True
    mock_sheets.write_stock_data.return_value = True
    mock_sheets.create_summary_sheet.return_value = True
    mock_sheets.clear_all_synthetic_data.return_value = True
    return mock_sheets

@pytest.fixture
def patch_env_vars():
    """Патчит переменные окружения для тестов"""
    with patch.dict(os.environ, {
        'OZON_CLIENT_ID': 'test_client_id',
        'OZON_API_KEY': 'test_api_key',
        'OZON_BASE_URL': 'https://api-seller.ozon.ru',
        'GOOGLE_SERVICE_ACCOUNT_JSON': 'test_service_account.json',
        'GOOGLE_SPREADSHEET_ID': 'test_spreadsheet_id',
        'TELEGRAM_TOKEN': 'test_telegram_token',
        'TELEGRAM_CHAT_ID': 'test_chat_id',
        'LOG_LEVEL': 'INFO',
        'CACHE_ENABLED': 'true',
        'API_MONITORING_ENABLED': 'true',
        'API_METRICS_ENABLED': 'true'
    }):
        yield 