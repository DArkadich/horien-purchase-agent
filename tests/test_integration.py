"""
Интеграционные тесты для проверки взаимодействия между модулями
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from forecast import PurchaseForecast
from cache_manager import CacheManager, CachedAPIClient
from ozon_api import OzonAPI
from telegram_notify import TelegramNotifier
from sheets import GoogleSheets
from stock_tracker import StockTracker

class TestForecastIntegration:
    """Интеграционные тесты для модуля прогнозирования"""
    
    @pytest.mark.integration
    def test_forecast_with_cache_integration(self, sample_sales_data, sample_stocks_data, test_cache_dir):
        """Тест интеграции прогнозирования с кэшированием"""
        # Создаем компоненты
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        mock_api = Mock()
        mock_api.get_products.return_value = [{"sku": "SKU_001", "name": "Product 1"}]
        mock_api.get_sales_data.return_value = sample_sales_data
        mock_api.get_stocks_data.return_value = sample_stocks_data
        
        cached_api = CachedAPIClient(mock_api, cache_manager)
        forecast = PurchaseForecast()
        
        # Получаем данные через кэшированный API
        sales_data = cached_api.get_sales_data_with_cache(days=30)
        stocks_data = cached_api.get_stocks_data_with_cache()
        
        # Подготавливаем данные
        sales_df = forecast.prepare_sales_data(sales_data)
        stocks_df = forecast.prepare_stocks_data(stocks_data)
        
        # Рассчитываем прогноз
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        
        # Генерируем отчет
        report = forecast.generate_purchase_report(forecast_df)
        
        # Проверяем результаты
        assert sales_data is not None
        assert stocks_data is not None
        assert len(forecast_df) > 0
        assert len(report) > 0
        
        # Проверяем, что данные кэшировались
        cache_stats = cache_manager.get_cache_stats()
        assert cache_stats['total_entries'] > 0
    
    @pytest.mark.integration
    def test_forecast_with_validation_integration(self, sample_sales_data, sample_stocks_data):
        """Тест интеграции прогнозирования с валидацией"""
        forecast = PurchaseForecast()
        
        # Валидируем входные данные
        from forecast import DataValidator
        sales_valid, sales_errors = DataValidator.validate_sales_data(sample_sales_data)
        stocks_valid, stocks_errors = DataValidator.validate_stocks_data(sample_stocks_data)
        
        assert sales_valid is True
        assert stocks_valid is True
        assert len(sales_errors) == 0
        assert len(stocks_errors) == 0
        
        # Подготавливаем данные
        sales_df = forecast.prepare_sales_data(sample_sales_data)
        stocks_df = forecast.prepare_stocks_data(sample_stocks_data)
        
        # Рассчитываем прогноз
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        
        # Валидируем результат прогноза
        forecast_valid, forecast_errors = forecast.validate_forecast_data(forecast_df)
        
        assert forecast_valid is True
        assert len(forecast_errors) == 0
    
    @pytest.mark.integration
    def test_forecast_analytics_integration(self, sample_sales_data, sample_stocks_data):
        """Тест интеграции прогнозирования с аналитикой"""
        forecast = PurchaseForecast()
        
        # Подготавливаем данные
        sales_df = forecast.prepare_sales_data(sample_sales_data)
        stocks_df = forecast.prepare_stocks_data(sample_stocks_data)
        
        # Рассчитываем прогноз
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        
        # Получаем аналитику
        analytics = forecast.get_forecast_analytics(forecast_df)
        seasonality = forecast.analyze_seasonality(sales_df)
        recommendations = forecast.get_forecast_recommendations(forecast_df)
        
        # Проверяем результаты
        assert isinstance(analytics, dict)
        assert isinstance(seasonality, dict)
        assert isinstance(recommendations, list)
        
        # Проверяем наличие ключевых полей в аналитике
        assert 'total_items' in analytics
        assert 'high_priority_count' in analytics
        assert 'medium_priority_count' in analytics
        assert 'low_priority_count' in analytics
        
        # Проверяем наличие ключевых полей в сезонности
        assert 'has_seasonality' in seasonality
        assert 'seasonality_strength' in seasonality

class TestAPIIntegration:
    """Интеграционные тесты для API"""
    
    @pytest.mark.integration
    @patch('ozon_api.OZON_CLIENT_ID', 'test_client_id')
    @patch('ozon_api.OZON_API_KEY', 'test_api_key')
    @patch('ozon_api.OZON_BASE_URL', 'https://api-seller.ozon.ru')
    def test_api_with_retry_integration(self):
        """Тест интеграции API с retry-логикой"""
        api = OzonAPI()
        
        # Проверяем, что retry manager инициализирован
        assert api.retry_manager is not None
        assert hasattr(api.retry_manager, 'max_retries')
        assert hasattr(api.retry_manager, 'base_delay')
        assert hasattr(api.retry_manager, 'max_delay')
    
    @pytest.mark.integration
    def test_api_with_cache_integration(self, test_cache_dir):
        """Тест интеграции API с кэшированием"""
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        mock_api = Mock()
        
        # Настраиваем мок API
        mock_api.get_products.return_value = [{"sku": "SKU_001", "name": "Product 1"}]
        mock_api.get_sales_data.return_value = [{"sku": "SKU_001", "date": "2024-01-01", "quantity": 10}]
        mock_api.get_stocks_data.return_value = [{"sku": "SKU_001", "stock": 50, "reserved": 10}]
        
        cached_api = CachedAPIClient(mock_api, cache_manager)
        
        # Первый запрос - должен вызвать API
        products1 = cached_api.get_products_with_cache()
        assert products1 is not None
        assert mock_api.get_products.call_count == 1
        
        # Второй запрос - должен использовать кэш
        products2 = cached_api.get_products_with_cache()
        assert products2 == products1
        assert mock_api.get_products.call_count == 1  # Не должно быть дополнительных вызовов
        
        # Принудительное обновление
        products3 = cached_api.get_products_with_cache(force_refresh=True)
        assert products3 == products1
        assert mock_api.get_products.call_count == 2  # Должен быть дополнительный вызов

class TestNotificationIntegration:
    """Интеграционные тесты для уведомлений"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_telegram_integration(self):
        """Тест интеграции с Telegram"""
        # Мокаем Telegram API
        with patch('telegram_notify.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock(return_value=True)
            mock_bot_class.return_value = mock_bot
            
            # Создаем уведомления
            telegram = TelegramNotifier()
            
            # Отправляем сообщение
            result = await telegram.send_message("Test message")
            
            assert result is True
            mock_bot.send_message.assert_called_once()
    
    @pytest.mark.integration
    def test_sheets_integration(self):
        """Тест интеграции с Google Sheets"""
        # Мокаем Google Sheets API
        with patch('sheets.build') as mock_build:
            mock_service = Mock()
            mock_spreadsheets = Mock()
            mock_values = Mock()
            
            mock_service.spreadsheets.return_value = mock_spreadsheets
            mock_spreadsheets.values.return_value = mock_values
            mock_build.return_value = mock_service
            
            # Создаем Google Sheets клиент
            sheets = GoogleSheets()
            
            # Тестируем запись данных
            test_data = [{"sku": "SKU_001", "quantity": 10}]
            result = sheets.write_purchase_report(test_data)
            
            assert result is True

class TestStockTrackerIntegration:
    """Интеграционные тесты для отслеживания остатков"""
    
    @pytest.mark.integration
    def test_stock_tracker_integration(self, test_data_dir):
        """Тест интеграции StockTracker"""
        stock_tracker = StockTracker(db_path=test_data_dir)
        
        # Тестовые данные об остатках
        test_stocks = [
            {"sku": "SKU_001", "stock": 50, "reserved": 10},
            {"sku": "SKU_002", "stock": 30, "reserved": 5}
        ]
        
        # Сохраняем данные
        stock_tracker.save_stock_data(test_stocks)
        
        # Получаем историю
        history = stock_tracker.get_stock_history(days=2)
        
        # Проверяем, что данные сохранились
        assert history is not None
        assert len(history) > 0
    
    @pytest.mark.integration
    def test_sales_estimation_integration(self, test_data_dir):
        """Тест интеграции оценки продаж"""
        stock_tracker = StockTracker(db_path=test_data_dir)
        
        # Сохраняем данные об остатках за несколько дней
        stocks_day1 = [{"sku": "SKU_001", "stock": 50, "reserved": 10}]
        stocks_day2 = [{"sku": "SKU_001", "stock": 45, "reserved": 8}]
        
        stock_tracker.save_stock_data(stocks_day1)
        stock_tracker.save_stock_data(stocks_day2)
        
        # Оцениваем продажи
        estimated_sales = stock_tracker.estimate_sales_from_stock_changes(days=2)
        
        # Проверяем результат
        assert estimated_sales is not None
        assert isinstance(estimated_sales, list)

class TestEndToEndIntegration:
    """End-to-end интеграционные тесты"""
    
    @pytest.mark.integration
    def test_full_forecast_workflow(self, sample_sales_data, sample_stocks_data, test_cache_dir):
        """Тест полного рабочего процесса прогнозирования"""
        # Создаем все компоненты
        cache_manager = CacheManager(cache_dir=test_cache_dir)
        mock_api = Mock()
        mock_api.get_products.return_value = [{"sku": "SKU_001", "name": "Product 1"}]
        mock_api.get_sales_data.return_value = sample_sales_data
        mock_api.get_stocks_data.return_value = sample_stocks_data
        
        cached_api = CachedAPIClient(mock_api, cache_manager)
        forecast = PurchaseForecast()
        
        # Получаем данные
        sales_data = cached_api.get_sales_data_with_cache(days=30)
        stocks_data = cached_api.get_stocks_data_with_cache()
        
        # Валидируем данные
        from forecast import DataValidator
        sales_valid, _ = DataValidator.validate_sales_data(sales_data)
        stocks_valid, _ = DataValidator.validate_stocks_data(stocks_data)
        
        assert sales_valid is True
        assert stocks_valid is True
        
        # Подготавливаем данные
        sales_df = forecast.prepare_sales_data(sales_data)
        stocks_df = forecast.prepare_stocks_data(stocks_data)
        
        # Рассчитываем прогноз
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        
        # Валидируем прогноз
        forecast_valid, _ = forecast.validate_forecast_data(forecast_df)
        assert forecast_valid is True
        
        # Генерируем отчет
        report = forecast.generate_purchase_report(forecast_df)
        
        # Получаем аналитику
        analytics = forecast.get_forecast_analytics(forecast_df)
        
        # Проверяем результаты
        assert len(forecast_df) > 0
        assert len(report) > 0
        assert analytics['total_items'] > 0
        
        # Проверяем кэширование
        cache_stats = cache_manager.get_cache_stats()
        assert cache_stats['total_entries'] > 0 