"""
Unit-тесты для модуля ozon_api.py
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from ozon_api import OzonAPI, RetryManager

class TestRetryManager:
    """Тесты для RetryManager"""
    
    @pytest.mark.unit
    def test_init(self):
        """Тест инициализации RetryManager"""
        retry_manager = RetryManager(max_retries=5, base_delay=2.0, max_delay=60.0)
        
        assert retry_manager.max_retries == 5
        assert retry_manager.base_delay == 2.0
        assert retry_manager.max_delay == 60.0
    
    @pytest.mark.unit
    def test_should_retry_status_code(self):
        """Тест определения необходимости повтора по статус коду"""
        retry_manager = RetryManager()
        
        # Коды, которые должны вызывать повторы
        assert retry_manager.should_retry_status_code(500) is True
        assert retry_manager.should_retry_status_code(502) is True
        assert retry_manager.should_retry_status_code(503) is True
        assert retry_manager.should_retry_status_code(504) is True
        assert retry_manager.should_retry_status_code(429) is True
        
        # Коды, которые не должны вызывать повторы
        assert retry_manager.should_retry_status_code(200) is False
        assert retry_manager.should_retry_status_code(400) is False
        assert retry_manager.should_retry_status_code(404) is False
    
    @pytest.mark.unit
    def test_should_retry_exception(self):
        """Тест определения необходимости повтора по исключению"""
        retry_manager = RetryManager()
        
        # Исключения, которые должны вызывать повторы
        assert retry_manager.should_retry_exception(requests.exceptions.ConnectionError()) is True
        assert retry_manager.should_retry_exception(requests.exceptions.Timeout()) is True
        assert retry_manager.should_retry_exception(requests.exceptions.ConnectTimeout()) is True
        assert retry_manager.should_retry_exception(requests.exceptions.ReadTimeout()) is True
        
        # Исключения, которые не должны вызывать повторы
        assert retry_manager.should_retry_exception(ValueError()) is False
        assert retry_manager.should_retry_exception(TypeError()) is False
    
    @pytest.mark.unit
    def test_execute_with_retry_success_first_attempt(self):
        """Тест успешного выполнения с первой попытки"""
        retry_manager = RetryManager()
        
        mock_func = Mock(return_value="success")
        
        result = retry_manager.execute_with_retry(mock_func, "arg1", kwarg="value")
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.unit
    def test_execute_with_retry_success_after_retries(self):
        """Тест успешного выполнения после повторов"""
        retry_manager = RetryManager(max_retries=2)
        
        mock_func = Mock()
        mock_func.side_effect = [
            requests.exceptions.ConnectionError(),
            requests.exceptions.Timeout(),
            "success"
        ]
        
        result = retry_manager.execute_with_retry(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    @pytest.mark.unit
    def test_execute_with_retry_max_retries_exceeded(self):
        """Тест превышения максимального количества повторов"""
        retry_manager = RetryManager(max_retries=2)
        
        mock_func = Mock()
        mock_func.side_effect = requests.exceptions.ConnectionError()
        
        result = retry_manager.execute_with_retry(mock_func)
        
        assert result is None
        assert mock_func.call_count == 3  # 1 + 2 повтора
    
    @pytest.mark.unit
    def test_execute_with_retry_unexpected_exception(self):
        """Тест неожиданного исключения"""
        retry_manager = RetryManager()
        
        mock_func = Mock()
        mock_func.side_effect = ValueError("Unexpected error")
        
        result = retry_manager.execute_with_retry(mock_func)
        
        assert result is None
        assert mock_func.call_count == 1  # Не повторяем для неожиданных ошибок

class TestOzonAPI:
    """Тесты для OzonAPI"""
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_init(self):
        """Тест инициализации OzonAPI"""
        api = OzonAPI()
        
        assert api.client_id == 'test_client_id'
        assert api.api_key == 'test_api_key'
        assert api.base_url == 'https://api-seller.ozon.ru'
        assert api.retry_manager is not None
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_make_single_request_success(self):
        """Тест успешного выполнения запроса"""
        api = OzonAPI()
        
        # Мокаем requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = api._make_single_request("/test/endpoint", {"test": "data"})
            
            assert result == {"result": "success"}
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_make_single_request_error_status(self):
        """Тест запроса с ошибкой статуса"""
        api = OzonAPI()
        
        # Мокаем requests.post с ошибкой
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = api._make_single_request("/test/endpoint", {"test": "data"})
            
            assert result is None
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_make_single_request_connection_error(self):
        """Тест запроса с ошибкой соединения"""
        api = OzonAPI()
        
        # Мокаем requests.post с исключением
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError()) as mock_post:
            result = api._make_single_request("/test/endpoint", {"test": "data"})
            
            assert result is None
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_products_success(self):
        """Тест успешного получения товаров"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_products = [
            {"sku": "SKU_001", "name": "Product 1"},
            {"sku": "SKU_002", "name": "Product 2"}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_products}}):
            result = api.get_products()
            
            assert result == mock_products
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_products_failure(self):
        """Тест неудачного получения товаров"""
        api = OzonAPI()
        
        # Мокаем _make_request с ошибкой
        with patch.object(api, '_make_request', return_value=None):
            result = api.get_products()
            
            assert result is None
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_sales_data_success(self):
        """Тест успешного получения данных о продажах"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_sales = [
            {"sku": "SKU_001", "date": "2024-01-01", "quantity": 10},
            {"sku": "SKU_002", "date": "2024-01-01", "quantity": 5}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_sales}}):
            result = api.get_sales_data(days=30)
            
            assert result == mock_sales
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_stocks_data_success(self):
        """Тест успешного получения данных об остатках"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_stocks = [
            {"sku": "SKU_001", "stock": 50, "reserved": 10},
            {"sku": "SKU_002", "stock": 30, "reserved": 5}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_stocks}}):
            result = api.get_stocks_data()
            
            assert result == mock_stocks
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_product_info_success(self):
        """Тест успешного получения информации о товарах"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_info = [
            {"sku": "SKU_001", "name": "Product 1", "price": 100},
            {"sku": "SKU_002", "name": "Product 2", "price": 200}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_info}}):
            result = api.get_product_info(["SKU_001", "SKU_002"])
            
            assert result == mock_info
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_analytics_data_success(self):
        """Тест успешного получения аналитических данных"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_analytics = [
            {"sku": "SKU_001", "views": 100, "sales": 10},
            {"sku": "SKU_002", "views": 200, "sales": 20}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_analytics}}):
            result = api.get_analytics_data(days=30)
            
            assert result == mock_analytics
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_create_products_report_success(self):
        """Тест успешного создания отчета о товарах"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_report_id = "report_123"
        
        with patch.object(api, '_make_request', return_value={"result": {"report_id": mock_report_id}}):
            result = api.create_products_report()
            
            assert result == mock_report_id
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_report_status_success(self):
        """Тест успешного получения статуса отчета"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_status = {"status": "completed", "progress": 100}
        
        with patch.object(api, '_make_request', return_value={"result": mock_status}):
            result = api.get_report_status("report_123")
            
            assert result == mock_status
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_get_report_file_success(self):
        """Тест успешного получения файла отчета"""
        api = OzonAPI()
        
        # Мокаем _make_request
        mock_file_data = [
            {"sku": "SKU_001", "name": "Product 1"},
            {"sku": "SKU_002", "name": "Product 2"}
        ]
        
        with patch.object(api, '_make_request', return_value={"result": {"items": mock_file_data}}):
            result = api.get_report_file("report_123")
            
            assert result == mock_file_data
    
    @pytest.mark.unit
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_request_headers(self):
        """Тест заголовков запроса"""
        api = OzonAPI()
        
        # Мокаем requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            api._make_single_request("/test/endpoint", {"test": "data"})
            
            # Проверяем, что заголовки переданы корректно
            call_args = mock_post.call_args
            headers = call_args[1]['headers']
            
            assert 'Client-Id' in headers
            assert 'Api-Key' in headers
            assert 'Content-Type' in headers
            assert headers['Client-Id'] == 'test_client_id'
            assert headers['Api-Key'] == 'test_api_key'
            assert headers['Content-Type'] == 'application/json' 