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
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Пробуем различные эндпоинты для получения продаж
        endpoints_to_try = [
            ("/v1/sales/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            }),
            ("/v2/sales/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            }),
            ("/v3/sales/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            }),
            ("/v1/analytics/sales", {
                "date_from": start_date.strftime("%Y-%m-%d"),
                "date_to": end_date.strftime("%Y-%m-%d")
            }),
            ("/v1/report/list", {
                "report_type": "SELLER_SALES",
                "page_size": 1000,
                "page": 1
            }),
            # Также пробуем заказы как fallback
            ("/v1/order/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            }),
            ("/v2/order/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            }),
            ("/v3/order/list", {
                "limit": 1000,
                "offset": 0,
                "since": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            })
        ]
        
        for endpoint, data in endpoints_to_try:
            logger.info(f"Пробуем эндпоинт: {endpoint}")
            result = self._make_request(endpoint, data)
            
            sales_data = []
            
            # Обрабатываем разные форматы ответов
            if result:
                # Формат с orders
                if "orders" in result and result["orders"]:
                    for order in result["orders"]:
                        if "items" in order:
                            for item in order["items"]:
                                sales_data.append({
                                    "sku": item.get("offer_id", ""),
                                    "date": order.get("created_at", "").split("T")[0],
                                    "quantity": item.get("quantity", 0),
                                    "revenue": item.get("price", {}).get("price", 0)
                                })
                
                # Формат с sales
                elif "sales" in result and result["sales"]:
                    for sale in result["sales"]:
                        sales_data.append({
                            "sku": sale.get("offer_id", ""),
                            "date": sale.get("date", ""),
                            "quantity": sale.get("quantity", 0),
                            "revenue": sale.get("revenue", 0)
                        })
                
                # Формат с items
                elif "items" in result and result["items"]:
                    for item in result["items"]:
                        sales_data.append({
                            "sku": item.get("offer_id", ""),
                            "date": item.get("date", ""),
                            "quantity": item.get("quantity", 0),
                            "revenue": item.get("revenue", 0)
                        })
                
                # Формат аналитики
                elif "data" in result and result["data"]:
                    for data_point in result["data"]:
                        sales_data.append({
                            "sku": data_point.get("sku", ""),
                            "date": data_point.get("date", ""),
                            "quantity": data_point.get("quantity", 0),
                            "revenue": data_point.get("revenue", 0)
                        })
            
            if sales_data:
                logger.info(f"Получено {len(sales_data)} записей о продажах из {endpoint}")
                return sales_data
        
        # Если ни один эндпоинт не работает, возвращаем пустой список
        logger.warning("Не удалось получить данные о продажах ни из одного эндпоинта")
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
        logger.info("Получение данных об остатках...")
        
        # Получаем реальные товары
        products = self.get_products()
        if not products:
            logger.error("Не удалось получить список товаров")
            return []
        
        # Попробуем получить реальные остатки через отчёт
        endpoint = "/v1/report/list"
        data = {
            "report_type": "SELLER_STOCK",
            "page_size": 100,
            "page": 1
        }
        
        result = self._make_request(endpoint, data)
        if result and "items" in result and result["items"]:
            stocks_data = []
            for item in result["items"]:
                stocks_data.append({
                    "sku": item.get("offer_id", ""),
                    "stock": item.get("stock", 0),
                    "reserved": item.get("reserved", 0)
                })
            
            if stocks_data:
                logger.info(f"Получено {len(stocks_data)} записей об остатках из API")
                return stocks_data
        
        # Если нет данных из API, возвращаем пустой список
        logger.warning("Нет данных об остатках из API")
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