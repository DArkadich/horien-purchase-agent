"""
Модуль для работы с Ozon Seller API
"""

import requests
import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from config import (
    OZON_CLIENT_ID, OZON_API_KEY, OZON_BASE_URL,
    API_MAX_RETRIES, API_BASE_DELAY, API_MAX_DELAY, API_TIMEOUT,
    logger
)
from api_metrics import APIMetricsCollector, MetricType

class RetryManager:
    """Менеджер для управления повторными попытками API запросов"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Выполняет функцию с повторными попытками при ошибках
        
        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат функции или None при неудаче
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # Если получили результат, возвращаем его
                if result is not None:
                    if attempt > 0:
                        logger.info(f"Успешно выполнен запрос после {attempt} повторных попыток")
                    return result
                
                # Если результат None, но нет исключения, это может быть нормально
                # (например, API вернул пустой список)
                if attempt == 0:
                    return None
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries + 1} не удалась: {e}")
                
                # Если это последняя попытка, логируем ошибку и возвращаем None
                if attempt == self.max_retries:
                    logger.error(f"Все попытки исчерпаны. Последняя ошибка: {e}")
                    return None
                
                # Вычисляем задержку с экспоненциальным откатом
                delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 1), self.max_delay)
                logger.info(f"Ожидание {delay:.2f} секунд перед следующей попыткой...")
                time.sleep(delay)
            
            except Exception as e:
                last_exception = e
                logger.error(f"Неожиданная ошибка в попытке {attempt + 1}: {e}")
                
                # Для неожиданных ошибок не делаем повторные попытки
                return None
        
        return None
    
    def should_retry_status_code(self, status_code: int) -> bool:
        """
        Определяет, нужно ли повторять запрос при данном статус коде
        """
        # Повторяем для временных ошибок сервера
        retryable_codes = {500, 502, 503, 504, 429}
        return status_code in retryable_codes
    
    def should_retry_exception(self, exception: Exception) -> bool:
        """
        Определяет, нужно ли повторять запрос при данном исключении
        """
        # Повторяем для сетевых ошибок
        retryable_exceptions = (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
        )
        return isinstance(exception, retryable_exceptions)

class OzonAPI:
    """Класс для работы с Ozon Seller API"""
    
    def __init__(self):
        self.client_id = OZON_CLIENT_ID
        self.api_key = OZON_API_KEY
        self.base_url = OZON_BASE_URL
        self.retry_manager = RetryManager(
            max_retries=API_MAX_RETRIES,
            base_delay=API_BASE_DELAY,
            max_delay=API_MAX_DELAY
        )
        self.metrics_collector = APIMetricsCollector()
    
    def _make_single_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Выполняет один запрос к API"""
        start_time = time.time()
        
        try:
            headers = {
                "Client-Id": self.client_id,
                "Api-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=data,
                timeout=API_TIMEOUT
            )
            
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            # Записываем метрику времени ответа
            self.metrics_collector.record_response_time(
                endpoint, response_time, response.status_code
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                # Записываем метрику ошибки
                self.metrics_collector.record_response_time(
                    endpoint, response_time, response.status_code, 
                    f"HTTP {response.status_code}: {response.text}"
                )
                logger.error(f"Ошибка {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            response_time = (time.time() - start_time) * 1000
            
            # Записываем метрику ошибки
            self.metrics_collector.record_response_time(
                endpoint, response_time, None, str(e)
            )
            
            raise
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к Ozon API с retry-логикой
        """
        logger.info(f"Выполнение запроса к {endpoint} с retry-логикой")
        
        return self.retry_manager.execute_with_retry(
            self._make_single_request, endpoint, data
        )
    
    def get_products(self) -> List[Dict[str, Any]]:
        """Получает список товаров"""
        logger.info("Получение списка товаров...")
        
        endpoint = "/v3/product/list"
        data = {
            "limit": 1000,
            "offset": 0
        }
        
        try:
            result = self._make_request(endpoint, data)
            
            if result and isinstance(result, dict):
                # Записываем метрику успешности
                self.metrics_collector.record_success_rate("get_products", 1, 1)
                
                # Проверяем структуру ответа
                if "items" in result:
                    products = result["items"]
                    logger.info(f"Получено {len(products)} товаров")
                    return products
                elif "result" in result and "items" in result["result"]:
                    products = result["result"]["items"]
                    logger.info(f"Получено {len(products)} товаров")
                    return products
                else:
                    logger.warning(f"Неожиданная структура ответа API: {list(result.keys())}")
                    return []
            else:
                # Записываем метрику ошибки
                self.metrics_collector.record_success_rate("get_products", 0, 1)
                logger.warning("Не удалось получить товары через API")
                return []
                
        except Exception as e:
            # Записываем метрику ошибки
            self.metrics_collector.record_success_rate("get_products", 0, 1)
            logger.error(f"API недоступен или возвращает ошибку. Проверьте настройки API ключей и доступность сервиса.")
            return []
    
    def get_sales_data(self, days: int = 180) -> List[Dict[str, Any]]:
        """
        Получает данные о продажах за указанное количество дней через аналитический API
        """
        logger.info(f"Получение данных о продажах за {days} дней через аналитический API...")
        
        try:
            # Получаем аналитические данные
            analytics_data = self.get_analytics_data(days=min(days, 90))  # API ограничен 90 днями
            
            if not analytics_data:
                logger.warning("Не удалось получить аналитические данные из API")
                logger.error("Проверьте доступность аналитического API и права доступа")
                return []
            
            # Преобразуем аналитические данные в формат продаж
            sales_data = []
            for record in analytics_data:
                # Проверяем наличие необходимых полей
                if 'day' in record and 'sku' in record and 'orders' in record:
                    sales_data.append({
                        "sku": record['sku'],
                        "date": record['day'],
                        "quantity": record.get('orders', 0),  # Количество заказов как количество продаж
                        "revenue": record.get('revenue', 0)
                    })
            
            logger.info(f"Преобразовано {len(sales_data)} записей о продажах из аналитических данных")
            
            if sales_data:
                # Логируем примеры для отладки
                for i, sale in enumerate(sales_data[:3]):
                    logger.info(f"Пример продажи {i+1}: SKU={sale['sku']}, Дата={sale['date']}, Количество={sale['quantity']}")
            else:
                logger.warning("Нет данных о продажах в аналитических данных")
            
            return sales_data
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных о продажах: {e}")
            logger.error("Проверьте подключение к API и корректность запроса")
            return []
    
    def get_stocks_data(self) -> List[Dict[str, Any]]:
        """
        Получает данные об остатках товаров
        """
        try:
            logger.info("Получение данных об остатках...")
            
            # Получаем список товаров
            products = self.get_products()
            if not products:
                logger.warning("Нет товаров для получения остатков")
                return []
            
            # Извлекаем ID товаров (используем offer_id)
            product_ids = [product.get('offer_id') for product in products if product.get('offer_id')]
            
            # Отладочная информация
            logger.info(f"Получено {len(products)} товаров")
            if products:
                logger.info(f"Пример структуры товара: {list(products[0].keys())}")
                logger.info(f"Первый товар: {products[0]}")
            
            logger.info(f"Извлечено {len(product_ids)} offer_id товаров: {product_ids[:5]}")  # Показываем первые 5
            
            if not product_ids:
                logger.warning("Нет offer_id товаров для получения остатков")
                return []
            
            # Получаем информацию о товарах с остатками
            logger.info(f"Вызываем get_product_info с {len(product_ids)} offer_id")
            product_info = self.get_product_info(product_ids)
            logger.info(f"Получено {len(product_info)} товаров из product_info")
            
            if not product_info:
                logger.warning("Не удалось получить информацию о товарах")
                return []
            
            stocks_data = []
            for product in product_info:
                # Используем offer_id как SKU
                sku = product.get('offer_id', '')
                name = product.get('name', '')
                
                # Отладочная информация для каждого товара
                logger.info(f"Обработка товара: SKU={sku}, Name={name}")
                
                if 'stocks' in product:
                    stocks = product['stocks']
                    logger.info(f"Stocks структура: has_stock={stocks.get('has_stock')}, stocks_array={len(stocks.get('stocks', []))}")
                    
                    if 'stocks' in stocks and isinstance(stocks['stocks'], list) and stocks['stocks']:
                        # Новый формат с массивом stocks
                        logger.info(f"Найдено {len(stocks['stocks'])} элементов в stocks array")
                        for i, stock_item in enumerate(stocks['stocks']):
                            logger.info(f"Stock item {i+1}: {stock_item}")
                            present = stock_item.get('present', 0)
                            reserved = stock_item.get('reserved', 0)
                            logger.info(f"Товар {sku}: present={present}, reserved={reserved}")
                            stocks_data.append({
                                "sku": sku,
                                "name": name,
                                "stock": present,
                                "reserved": reserved
                            })
                    elif 'has_stock' in stocks and stocks['has_stock']:
                        # Есть остатки, но нет детальной информации
                        logger.info(f"Товар {sku} имеет остатки (has_stock=True)")
                        stocks_data.append({
                            "sku": sku,
                            "name": name,
                            "stock": 1,  # Минимальное значение
                            "reserved": 0
                        })
                    else:
                        # Нет остатков - все равно добавляем товар с нулевыми остатками
                        logger.info(f"Товар {sku} не имеет остатков - добавляем с нулевыми остатками")
                        stocks_data.append({
                            "sku": sku,
                            "name": name,
                            "stock": 0,
                            "reserved": 0
                        })
                else:
                    logger.info(f"Товар {sku} не имеет поля stocks - добавляем с нулевыми остатками")
                    stocks_data.append({
                        "sku": sku,
                        "name": name,
                        "stock": 0,
                        "reserved": 0
                    })
            
            logger.info(f"Итоговое количество записей об остатках: {len(stocks_data)}")
            if stocks_data:
                logger.info(f"Получено {len(stocks_data)} записей об остатках из product_info")
                # Логируем несколько примеров
                for i, stock_item in enumerate(stocks_data[:3]):
                    logger.info(f"Пример остатка {i+1}: {stock_item}")
                return stocks_data
            
            logger.warning("Не удалось получить данные об остатках из product_info")
            return []
            
        except Exception as e:
            logger.error(f"Ошибка при получении остатков: {e}")
            return []
    
    def get_product_info(self, offer_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Получает детальную информацию о товарах по offer_id
        """
        logger.info(f"Получение информации о {len(offer_ids)} товарах по offer_id...")
        
        # Используем endpoint для получения информации по offer_id
        endpoint = "/v3/product/info/list"
        data = {
            "offer_id": offer_ids
        }
        
        logger.info(f"Отправляем запрос на {endpoint} с данными: {data}")
        result = self._make_request(endpoint, data)
        logger.info(f"Получен ответ от API: {result is not None}")
        
        if result and "items" in result:
            logger.info(f"Получена информация о {len(result['items'])} товарах")
            
            # Логируем структуру первого товара для отладки
            if result['items']:
                first_item = result['items'][0]
                logger.info(f"Первый товар: offer_id={first_item.get('offer_id')}, name={first_item.get('name')}")
                if 'stocks' in first_item:
                    stocks = first_item['stocks']
                    logger.info(f"Stocks первого товара: has_stock={stocks.get('has_stock')}, stocks_count={len(stocks.get('stocks', []))}")
            
            return result["items"]
        else:
            logger.warning(f"Не удалось получить информацию о товарах. Результат: {result}")
        return []
    
    def get_analytics_data(self, days: int = 180) -> List[Dict[str, Any]]:
        """
        Получает аналитические данные о продажах с retry-логикой
        """
        logger.info(f"Получение аналитических данных за {days} дней...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        endpoint = "/v1/analytics/data"
        data = {
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
            "metrics": ["revenue", "orders", "views"],
            "dimension": ["day", "sku"],
            "filters": [],
            "sort": [{"key": "day", "order": "ASC"}],
            "limit": 1000,
            "offset": 0
        }
        
        analytics_data = []
        offset = 0
        max_pages = 10  # Ограничиваем количество страниц для предотвращения бесконечного цикла
        
        for page in range(max_pages):
            data["offset"] = offset
            
            # Используем retry-логику для каждого запроса
            result = self.retry_manager.execute_with_retry(
                self._make_single_request, endpoint, data
            )
            
            if not result or "data" not in result:
                logger.warning(f"Не удалось получить данные для страницы {page + 1}")
                break
                
            page_data = result["data"]
            analytics_data.extend(page_data)
            
            logger.info(f"Получена страница {page + 1}: {len(page_data)} записей")
            
            # Если получили меньше записей чем лимит, значит это последняя страница
            if len(page_data) < 1000:
                break
                
            offset += 1000
            
            # Небольшая пауза между запросами для избежания rate limiting
            if page < max_pages - 1:
                time.sleep(0.5)
        
        logger.info(f"Получено {len(analytics_data)} записей аналитических данных за {page + 1} страниц")
        return analytics_data

    def create_products_report(self) -> Optional[str]:
        """
        Создает отчет о товарах через /v1/report/products/create с retry-логикой
        Возвращает ID отчета для последующего получения
        """
        logger.info("Создание отчета о товарах...")
        
        endpoint = "/v1/report/products/create"
        data = {
            "language": "DEFAULT"
        }
        
        logger.info(f"Отправка запроса на {endpoint} с данными: {data}")
        
        # Используем retry-логику для создания отчета
        result = self.retry_manager.execute_with_retry(
            self._make_single_request, endpoint, data
        )
        
        logger.info(f"Ответ API: {result}")
        
        if result and "result" in result:
            report_id = result["result"].get("report_id")
            if report_id:
                logger.info(f"Отчет о товарах создан, ID: {report_id}")
                return report_id
            else:
                logger.error(f"Нет report_id в ответе: {result}")
        else:
            logger.error(f"Неверный формат ответа: {result}")
        
        logger.error("Не удалось создать отчет о товарах")
        return None
    
    def get_report_status(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет статус отчета с retry-логикой
        """
        logger.info(f"Проверка статуса отчета {report_id}...")
        
        endpoint = "/v1/report/info"
        data = {
            "report_id": report_id
        }
        
        # Используем retry-логику для проверки статуса
        result = self.retry_manager.execute_with_retry(
            self._make_single_request, endpoint, data
        )
        
        if result and "result" in result:
            status = result["result"].get("status")
            logger.info(f"Статус отчета {report_id}: {status}")
            return result["result"]
        else:
            logger.error(f"Не удалось получить статус отчета {report_id}")
            return None
    
    def get_report_file(self, report_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Получает файл отчета с retry-логикой
        """
        logger.info(f"Получение файла отчета {report_id}...")
        
        endpoint = "/v1/report/info"
        data = {
            "report_id": report_id
        }
        
        # Используем retry-логику для получения файла
        result = self.retry_manager.execute_with_retry(
            self._make_single_request, endpoint, data
        )
        
        if result and "result" in result:
            report_info = result["result"]
            status = report_info.get("status")
            
            if status == "success":
                # Здесь должна быть логика для скачивания файла
                # Пока возвращаем информацию об отчете
                logger.info(f"Отчет {report_id} готов к скачиванию")
                return [report_info]
            elif status == "pending":
                logger.info(f"Отчет {report_id} еще в обработке")
                return None
            else:
                logger.warning(f"Отчет {report_id} имеет статус: {status}")
                return None
        else:
            logger.error(f"Не удалось получить файл отчета {report_id}")
            return None 