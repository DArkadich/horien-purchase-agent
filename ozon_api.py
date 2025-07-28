"""
Модуль для работы с Ozon Seller API
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config import OZON_API_KEY, OZON_CLIENT_ID, logger

class OzonAPI:
    """Класс для работы с Ozon Seller API"""
    
    def __init__(self):
        self.api_key = OZON_API_KEY
        self.client_id = OZON_CLIENT_ID
        self.base_url = "https://api-seller.ozon.ru"
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к Ozon API
        """
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.post(url, headers=self.headers, json=data)
            
            # Логируем детали запроса для отладки
            logger.debug(f"API Request: {url}")
            logger.debug(f"Request data: {data}")
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result"):
                    return result["result"]
                else:
                    logger.error(f"API вернул ошибку: {result}")
                    return None
            elif response.status_code == 404:
                logger.warning(f"Эндпоинт {endpoint} не найден (404). Возможно, используется неправильная версия API.")
                logger.debug(f"Response body: {response.text}")
                return None
            elif response.status_code == 401:
                logger.error(f"Ошибка аутентификации (401). Проверьте API ключи.")
                logger.debug(f"Response body: {response.text}")
                return None
            elif response.status_code == 403:
                logger.error(f"Ошибка доступа (403). Проверьте права доступа к API.")
                logger.debug(f"Response body: {response.text}")
                return None
            else:
                logger.error(f"API вернул статус {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к Ozon API: {e}")
            return None
    
    def get_products(self) -> List[Dict[str, Any]]:
        """
        Получает список всех товаров
        """
        logger.info("Получение списка товаров...")
        
        # Используем правильный эндпоинт для получения товаров
        endpoint = "/v3/product/list"
        data = {
            "limit": 1000,
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
        
        result = self._make_request(endpoint, data)
        if result and "items" in result:
            logger.info(f"Успешно получены товары: {len(result['items'])} шт")
            # Логируем первые несколько товаров для отладки
            for i, product in enumerate(result["items"][:3]):
                logger.debug(f"Товар {i+1}: ID={product.get('id')}, Offer={product.get('offer_id')}, Name={product.get('name')}")
            return result["items"]
        
        logger.warning("Не удалось получить товары через API, используем тестовые данные")
        return self._generate_test_products()
    
    def _generate_test_products(self) -> List[Dict[str, Any]]:
        """
        Генерирует тестовые данные товаров
        """
        test_skus = ["линза -3.5", "линза -3.0", "линза -2.5", "линза -2.0", "линза -1.5"]
        products = []
        
        for i, sku in enumerate(test_skus):
            products.append({
                "id": i + 1,
                "offer_id": sku,
                "name": f"Контактная линза {sku}",
                "status": "active"
            })
        
        return products
    
    def get_sales_data(self, days: int = 90) -> List[Dict[str, Any]]:
        """
        Получает данные о продажах за указанное количество дней
        """
        logger.info(f"Получение данных о продажах за {days} дней...")

        products = self.get_products()
        if not products:
            logger.warning("Нет товаров для оценки продаж")
            return []

        # Пока нет реальных данных о продажах, возвращаем пустой список
        logger.warning("Нет реальных данных о продажах из API")
        return []
    
    def _generate_test_sales_data(self, days: int) -> List[Dict[str, Any]]:
        """
        Генерирует тестовые данные о продажах для демонстрации
        """
        test_skus = ["линза -3.5", "линза -3.0", "линза -2.5", "линза -2.0", "линза -1.5"]
        sales_data = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            for sku in test_skus:
                # Генерируем случайные продажи
                import random
                quantity = random.randint(0, 5)
                revenue = quantity * random.randint(100, 500)
                
                sales_data.append({
                    "sku": sku,
                    "date": date.strftime("%Y-%m-%d"),
                    "quantity": quantity,
                    "revenue": revenue
                })
        
        return sales_data
    
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
            
            # Извлекаем ID товаров
            product_ids = [product.get('id') for product in products if product.get('id')]
            
            # Отладочная информация
            logger.info(f"Получено {len(products)} товаров")
            if products:
                logger.info(f"Пример структуры товара: {list(products[0].keys())}")
                logger.info(f"Первый товар: {products[0]}")
            
            logger.info(f"Извлечено {len(product_ids)} ID товаров: {product_ids[:5]}")  # Показываем первые 5
            
            if not product_ids:
                logger.warning("Нет ID товаров для получения остатков")
                return []
            
            # Получаем информацию о товарах с остатками
            product_info = self.get_product_info(product_ids)
            
            stocks_data = []
            for product in product_info:
                # Проверяем, есть ли ошибки в товаре
                if 'errors' in product and product['errors']:
                    logger.debug(f"Товар {product.get('id', 'unknown')} имеет ошибки: {product['errors']}")
                    continue
                
                # Используем offer_id как SKU
                sku = product.get('offer_id', '')
                
                if 'stocks' in product:
                    stocks = product['stocks']
                    if 'stocks' in stocks and isinstance(stocks['stocks'], list) and stocks['stocks']:
                        # Новый формат с массивом stocks
                        for stock_item in stocks['stocks']:
                            stocks_data.append({
                                "sku": sku,
                                "stock": stock_item.get('present', 0),
                                "reserved": stock_item.get('reserved', 0)
                            })
                    elif 'has_stock' in stocks and stocks['has_stock']:
                        # Есть остатки, но нет детальной информации
                        stocks_data.append({
                            "sku": sku,
                            "stock": 1,  # Минимальное значение
                            "reserved": 0
                        })
                    else:
                        # Старый формат или нет остатков
                        stocks_data.append({
                            "sku": sku,
                            "stock": stocks.get('stock', 0),
                            "reserved": stocks.get('reserved', 0)
                        })
            
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
    
    def _generate_test_stocks_data(self) -> List[Dict[str, Any]]:
        """
        Генерирует тестовые данные об остатках для демонстрации
        """
        test_skus = ["линза -3.5", "линза -3.0", "линза -2.5", "линза -2.0", "линза -1.5"]
        stocks_data = []
        
        import random
        for sku in test_skus:
            stock = random.randint(50, 200)
            reserved = random.randint(0, 20)
            
            stocks_data.append({
                "sku": sku,
                "stock": stock,
                "reserved": reserved
            })
        
        return stocks_data
    
    def get_product_info(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Получает детальную информацию о товарах
        """
        logger.info(f"Получение информации о {len(product_ids)} товарах...")
        
        endpoint = "/v3/product/info/list"
        data = {
            "product_id": product_ids
        }
        
        result = self._make_request(endpoint, data)
        
        if result and "items" in result:
            logger.info(f"Получена информация о {len(result['items'])} товарах")
            
            # Логируем структуру первого товара для отладки
            if result['items']:
                first_item = result['items'][0]
                logger.debug(f"Структура первого товара: {list(first_item.keys())}")
                if 'stocks' in first_item:
                    logger.debug(f"Структура stocks: {first_item['stocks']}")
            
            return result["items"]
        
        return []
    
    def get_analytics_data(self, days: int = 90) -> List[Dict[str, Any]]:
        """
        Получает аналитические данные о продажах
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
        
        while True:
            data["offset"] = offset
            result = self._make_request(endpoint, data)
            
            if not result or "data" not in result:
                break
                
            analytics_data.extend(result["data"])
            
            if len(result["data"]) < 1000:
                break
                
            offset += 1000
        
        logger.info(f"Получено {len(analytics_data)} записей аналитических данных")
        return analytics_data 

    def create_products_report(self) -> Optional[str]:
        """
        Создает отчет о товарах через /v1/report/products/create
        Возвращает ID отчета для последующего получения
        """
        logger.info("Создание отчета о товарах...")
        
        endpoint = "/v1/report/products/create"
        data = {
            "language": "DEFAULT"
        }
        
        logger.info(f"Отправка запроса на {endpoint} с данными: {data}")
        result = self._make_request(endpoint, data)
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
        Проверяет статус отчета
        """
        logger.info(f"Проверка статуса отчета {report_id}...")
        
        endpoint = "/v1/report/info"
        data = {
            "report_id": report_id
        }
        
        result = self._make_request(endpoint, data)
        
        if result and "result" in result:
            return result["result"]
        
        return None
    
    def get_report_file(self, report_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Получает файл отчета и парсит данные о товарах
        """
        logger.info(f"Получение файла отчета {report_id}...")
        
        # Сначала проверяем статус отчета
        status = self.get_report_status(report_id)
        if not status:
            logger.error("Не удалось получить статус отчета")
            return None
        
        # Проверяем, готов ли отчет
        if status.get("status") != "success":
            logger.info(f"Отчет еще не готов, статус: {status.get('status')}")
            return None
        
        # Получаем файл отчета
        file_url = status.get("file")
        if not file_url:
            logger.error("Нет ссылки на файл отчета")
            return None
        
        try:
            import requests
            response = requests.get(file_url)
            response.raise_for_status()
            
            # Парсим CSV файл
            import csv
            import io
            
            products_data = []
            csv_reader = csv.DictReader(io.StringIO(response.text))
            
            for row in csv_reader:
                # Парсим данные из CSV
                product_data = {
                    "sku": row.get("FBS Ozon SKU ID", ""),
                    "stock": int(row.get("Доступно на складе Ozon, шт", 0)),
                    "reserved": int(row.get("Зарезервировано, шт", 0)),
                    "price": float(row.get("Текущая цена с учётом скидки, руб.", 0)),
                    "status": row.get("Статус товара", ""),
                    "barcode": row.get("Barcode", ""),
                    "product_id": row.get("Ozon Product ID", "")
                }
                
                # Добавляем только товары с остатками
                if product_data["stock"] > 0 or product_data["reserved"] > 0:
                    products_data.append(product_data)
            
            logger.info(f"Получено {len(products_data)} товаров с остатками из отчета")
            return products_data
            
        except Exception as e:
            logger.error(f"Ошибка при получении файла отчета: {e}")
            return None 