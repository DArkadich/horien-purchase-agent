"""
Data Service - управление данными о товарах, продажах и остатках
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    Product, ProductList, SalesRecord, SalesData, 
    StockRecord, StockData, BaseResponse, ErrorResponse
)
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient, 
    DatabaseClient, handle_service_error, ServiceException
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('data-service', config['log_level'])

# Инициализация клиентов
redis_client = RedisClient(config['redis_url'])
rabbitmq_client = RabbitMQClient(config['rabbitmq_url'])
db_client = DatabaseClient(config['postgres_url'])

# ============================================================================
# FastAPI приложение
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    # Startup
    logger.info("Data Service запускается...")
    yield
    # Shutdown
    logger.info("Data Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="Data Service",
    description="Сервис для управления данными о товарах, продажах и остатках",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Зависимости
# ============================================================================

def get_redis_client() -> RedisClient:
    return redis_client

def get_rabbitmq_client() -> RabbitMQClient:
    return rabbitmq_client

def get_db_client() -> DatabaseClient:
    return db_client

# ============================================================================
# Эндпоинты для товаров
# ============================================================================

@app.get("/products", response_model=ProductList)
@handle_service_error
async def get_products(
    limit: int = 100,
    offset: int = 0,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение списка товаров"""
    logger.info(f"Запрос товаров: limit={limit}, offset={offset}")
    
    # Проверяем кэш
    cache_key = f"products:list:limit:{limit}:offset:{offset}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем данные из кэша")
        return ProductList(**cached_result)
    
    # Получаем данные из БД
    query = """
        SELECT sku, name, category, moq, created_at, updated_at
        FROM products
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """
    
    products_data = db_client.execute_query(query, {
        'limit': limit,
        'offset': offset
    })
    
    # Подсчитываем общее количество
    count_query = "SELECT COUNT(*) as total FROM products"
    count_result = db_client.execute_query(count_query)
    total = count_result[0]['total'] if count_result else 0
    
    # Формируем ответ
    products = [Product(**product) for product in products_data]
    response = ProductList(
        success=True,
        products=products,
        total=total
    )
    
    # Кэшируем результат
    redis_client.set(cache_key, response.dict(), ttl=300)  # 5 минут
    
    return response

@app.get("/products/{sku}", response_model=Product)
@handle_service_error
async def get_product(
    sku: str,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение товара по SKU"""
    logger.info(f"Запрос товара: {sku}")
    
    # Проверяем кэш
    cache_key = f"product:{sku}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем данные из кэша")
        return Product(**cached_result)
    
    # Получаем данные из БД
    query = """
        SELECT sku, name, category, moq, created_at, updated_at
        FROM products
        WHERE sku = :sku
    """
    
    products_data = db_client.execute_query(query, {'sku': sku})
    
    if not products_data:
        raise HTTPException(status_code=404, detail=f"Товар {sku} не найден")
    
    product = Product(**products_data[0])
    
    # Кэшируем результат
    redis_client.set(cache_key, product.dict(), ttl=600)  # 10 минут
    
    return product

# ============================================================================
# Эндпоинты для продаж
# ============================================================================

@app.get("/sales", response_model=SalesData)
@handle_service_error
async def get_sales(
    sku: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение данных о продажах"""
    logger.info(f"Запрос продаж: sku={sku}, start_date={start_date}, end_date={end_date}")
    
    # Формируем условия запроса
    conditions = []
    params = {'limit': limit}
    
    if sku:
        conditions.append("sku = :sku")
        params['sku'] = sku
    
    if start_date:
        conditions.append("date >= :start_date")
        params['start_date'] = start_date
    
    if end_date:
        conditions.append("date <= :end_date")
        params['end_date'] = end_date
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Проверяем кэш
    cache_key = f"sales:list:{hash(str(params))}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем данные из кэша")
        return SalesData(**cached_result)
    
    # Получаем данные из БД
    query = f"""
        SELECT sku, date, quantity, revenue, created_at
        FROM sales
        WHERE {where_clause}
        ORDER BY date DESC
        LIMIT :limit
    """
    
    sales_data = db_client.execute_query(query, params)
    
    # Подсчитываем общее количество
    count_query = f"SELECT COUNT(*) as total FROM sales WHERE {where_clause}"
    count_result = db_client.execute_query(count_query, params)
    total_records = count_result[0]['total'] if count_result else 0
    
    # Определяем диапазон дат
    if sales_data:
        dates = [datetime.fromisoformat(sale['date']) for sale in sales_data]
        date_range = {
            'start': min(dates).isoformat(),
            'end': max(dates).isoformat()
        }
    else:
        date_range = {'start': datetime.now().isoformat(), 'end': datetime.now().isoformat()}
    
    # Формируем ответ
    sales = [SalesRecord(**sale) for sale in sales_data]
    response = SalesData(
        success=True,
        sales=sales,
        total_records=total_records,
        date_range=date_range
    )
    
    # Кэшируем результат
    redis_client.set(cache_key, response.dict(), ttl=300)  # 5 минут
    
    return response

@app.get("/sales/{sku}", response_model=SalesData)
@handle_service_error
async def get_sales_by_sku(
    sku: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение продаж по конкретному SKU"""
    return await get_sales(sku, start_date, end_date, limit, redis_client, db_client)

# ============================================================================
# Эндпоинты для остатков
# ============================================================================

@app.get("/stocks", response_model=StockData)
@handle_service_error
async def get_stocks(
    sku: Optional[str] = None,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение данных об остатках"""
    logger.info(f"Запрос остатков: sku={sku}")
    
    # Проверяем кэш
    cache_key = f"stocks:list:{sku or 'all'}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем данные из кэша")
        return StockData(**cached_result)
    
    # Формируем запрос
    if sku:
        query = """
            SELECT sku, stock, reserved, available, updated_at
            FROM stocks
            WHERE sku = :sku
        """
        params = {'sku': sku}
    else:
        query = """
            SELECT sku, stock, reserved, available, updated_at
            FROM stocks
            ORDER BY updated_at DESC
        """
        params = {}
    
    stocks_data = db_client.execute_query(query, params)
    
    # Подсчитываем общее количество
    count_query = "SELECT COUNT(*) as total FROM stocks"
    if sku:
        count_query += " WHERE sku = :sku"
    
    count_result = db_client.execute_query(count_query, params)
    total_skus = count_result[0]['total'] if count_result else 0
    
    # Формируем ответ
    stocks = [StockRecord(**stock) for stock in stocks_data]
    response = StockData(
        success=True,
        stocks=stocks,
        total_skus=total_skus
    )
    
    # Кэшируем результат
    redis_client.set(cache_key, response.dict(), ttl=180)  # 3 минуты
    
    return response

@app.get("/stocks/{sku}", response_model=StockData)
@handle_service_error
async def get_stock_by_sku(
    sku: str,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение остатков по конкретному SKU"""
    return await get_stocks(sku, redis_client, db_client)

# ============================================================================
# Синхронизация с Ozon API
# ============================================================================

@app.post("/sync/ozon", response_model=BaseResponse)
@handle_service_error
async def sync_with_ozon(
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Запуск синхронизации с Ozon API"""
    logger.info("Запуск синхронизации с Ozon API")
    
    # Отправляем задачу в очередь
    event = {
        'event_type': 'sync_ozon',
        'service': 'data-service',
        'data': {
            'timestamp': datetime.now().isoformat(),
            'force_sync': True
        }
    }
    
    success = rabbitmq_client.publish_message('data.sync', event)
    
    if success:
        background_tasks.add_task(sync_ozon_data)
        return BaseResponse(
            success=True,
            message="Синхронизация с Ozon API запущена"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Ошибка отправки задачи синхронизации"
        )

async def sync_ozon_data():
    """Фоновая задача синхронизации данных"""
    logger.info("Начинаем синхронизацию данных с Ozon API")
    
    try:
        # Здесь будет логика синхронизации
        # Пока просто логируем
        logger.info("Синхронизация данных завершена")
        
        # Очищаем кэш
        redis_client.delete("products:list:*")
        redis_client.delete("sales:list:*")
        redis_client.delete("stocks:list:*")
        
        # Отправляем уведомление
        notification_event = {
            'event_type': 'sync_completed',
            'service': 'data-service',
            'data': {
                'message': 'Синхронизация с Ozon API завершена',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        rabbitmq_client.publish_message('notifications.send', notification_event)
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        
        # Отправляем уведомление об ошибке
        error_event = {
            'event_type': 'sync_error',
            'service': 'data-service',
            'data': {
                'message': f'Ошибка синхронизации: {e}',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        rabbitmq_client.publish_message('notifications.send', error_event)

# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "service": "data-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": config['version']
    }

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level=config['log_level'].lower()
    ) 