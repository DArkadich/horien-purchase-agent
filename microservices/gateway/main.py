"""
API Gateway - единая точка входа для всех запросов
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import httpx

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import BaseResponse, ErrorResponse
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient,
    handle_service_error, ServiceException
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('gateway', config['log_level'])

# Инициализация клиентов
redis_client = RedisClient(config['redis_url'])
rabbitmq_client = RabbitMQClient(config['rabbitmq_url'])

# Конфигурация сервисов
SERVICES = {
    'data': 'http://data-service:8001',
    'forecast': 'http://forecast-service:8002',
    'notification': 'http://notification-service:8003',
    'monitoring': 'http://monitoring-service:8004',
    'storage': 'http://storage-service:8005'
}

# ============================================================================
# FastAPI приложение
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    # Startup
    logger.info("API Gateway запускается...")
    yield
    # Shutdown
    logger.info("API Gateway останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="API Gateway",
    description="Единая точка входа для всех микросервисов",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # В продакшене указать конкретные хосты
)

# ============================================================================
# Зависимости
# ============================================================================

def get_redis_client() -> RedisClient:
    return redis_client

def get_rabbitmq_client() -> RabbitMQClient:
    return rabbitmq_client

# ============================================================================
# Утилиты для маршрутизации
# ============================================================================

async def forward_request(service: str, path: str, method: str, 
                         request: Request, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Перенаправляет запрос к соответствующему сервису"""
    service_url = SERVICES.get(service)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    target_url = f"{service_url}{path}"
    
    # Получаем заголовки запроса
    headers = dict(request.headers)
    # Удаляем заголовки, которые не должны передаваться
    headers.pop('host', None)
    headers.pop('content-length', None)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(target_url, headers=headers, params=request.query_params)
            elif method == "POST":
                response = await client.post(target_url, headers=headers, json=data)
            elif method == "PUT":
                response = await client.put(target_url, headers=headers, json=data)
            elif method == "DELETE":
                response = await client.delete(target_url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")
            
            # Логируем запрос
            logger.info(f"{method} {target_url} -> {response.status_code}")
            
            # Отправляем метрику
            metric_event = {
                'event_type': 'api_request',
                'service': 'gateway',
                'data': {
                    'target_service': service,
                    'method': method,
                    'path': path,
                    'status_code': response.status_code,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            rabbitmq_client.publish_message('monitoring.metrics', metric_event)
            
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )
            
            return response.json()
            
    except httpx.TimeoutException:
        logger.error(f"Timeout при обращении к сервису {service}")
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.ConnectError:
        logger.error(f"Ошибка подключения к сервису {service}")
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error(f"Ошибка при обращении к сервису {service}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# Эндпоинты для товаров (Data Service)
# ============================================================================

@app.get("/api/v1/products")
@handle_service_error
async def get_products(
    limit: int = 100,
    offset: int = 0,
    request: Request = None
):
    """Получение списка товаров"""
    path = f"/products?limit={limit}&offset={offset}"
    return await forward_request('data', path, 'GET', request)

@app.get("/api/v1/products/{sku}")
@handle_service_error
async def get_product(sku: str, request: Request = None):
    """Получение товара по SKU"""
    path = f"/products/{sku}"
    return await forward_request('data', path, 'GET', request)

# ============================================================================
# Эндпоинты для продаж (Data Service)
# ============================================================================

@app.get("/api/v1/sales")
@handle_service_error
async def get_sales(
    sku: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    request: Request = None
):
    """Получение данных о продажах"""
    params = []
    if sku:
        params.append(f"sku={sku}")
    if start_date:
        params.append(f"start_date={start_date}")
    if end_date:
        params.append(f"end_date={end_date}")
    params.append(f"limit={limit}")
    
    path = f"/sales?{'&'.join(params)}"
    return await forward_request('data', path, 'GET', request)

@app.get("/api/v1/sales/{sku}")
@handle_service_error
async def get_sales_by_sku(
    sku: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    request: Request = None
):
    """Получение продаж по конкретному SKU"""
    params = []
    if start_date:
        params.append(f"start_date={start_date}")
    if end_date:
        params.append(f"end_date={end_date}")
    params.append(f"limit={limit}")
    
    path = f"/sales/{sku}?{'&'.join(params)}"
    return await forward_request('data', path, 'GET', request)

# ============================================================================
# Эндпоинты для остатков (Data Service)
# ============================================================================

@app.get("/api/v1/stocks")
@handle_service_error
async def get_stocks(
    sku: Optional[str] = None,
    request: Request = None
):
    """Получение данных об остатках"""
    path = f"/stocks?sku={sku}" if sku else "/stocks"
    return await forward_request('data', path, 'GET', request)

@app.get("/api/v1/stocks/{sku}")
@handle_service_error
async def get_stock_by_sku(sku: str, request: Request = None):
    """Получение остатков по конкретному SKU"""
    path = f"/stocks/{sku}"
    return await forward_request('data', path, 'GET', request)

# ============================================================================
# Эндпоинты для прогнозов (Forecast Service)
# ============================================================================

@app.post("/api/v1/forecast")
@handle_service_error
async def calculate_forecast(
    request_data: Dict[str, Any],
    request: Request = None
):
    """Расчет прогноза закупок"""
    path = "/forecast/calculate"
    return await forward_request('forecast', path, 'POST', request, request_data)

@app.get("/api/v1/forecast/reports")
@handle_service_error
async def get_forecast_reports(
    limit: int = 100,
    request: Request = None
):
    """Получение отчетов о прогнозах"""
    path = f"/forecast/reports?limit={limit}"
    return await forward_request('forecast', path, 'GET', request)

@app.get("/api/v1/forecast/analytics")
@handle_service_error
async def get_forecast_analytics(request: Request = None):
    """Получение аналитики по прогнозам"""
    path = "/forecast/analytics"
    return await forward_request('forecast', path, 'GET', request)

@app.get("/api/v1/forecast/recommendations")
@handle_service_error
async def get_forecast_recommendations(request: Request = None):
    """Получение рекомендаций по прогнозам"""
    path = "/forecast/recommendations"
    return await forward_request('forecast', path, 'GET', request)

# ============================================================================
# Эндпоинты для уведомлений (Notification Service)
# ============================================================================

@app.post("/api/v1/notifications")
@handle_service_error
async def send_notification(
    notification_data: Dict[str, Any],
    request: Request = None
):
    """Отправка уведомления"""
    path = "/notifications/send"
    return await forward_request('notification', path, 'POST', request, notification_data)

@app.get("/api/v1/notifications/history")
@handle_service_error
async def get_notification_history(
    limit: int = 100,
    request: Request = None
):
    """Получение истории уведомлений"""
    path = f"/notifications/history?limit={limit}"
    return await forward_request('notification', path, 'GET', request)

# ============================================================================
# Эндпоинты для мониторинга (Monitoring Service)
# ============================================================================

@app.get("/api/v1/monitoring/health")
@handle_service_error
async def get_health_status(request: Request = None):
    """Получение статуса здоровья всех сервисов"""
    path = "/health"
    return await forward_request('monitoring', path, 'GET', request)

@app.get("/api/v1/monitoring/metrics")
@handle_service_error
async def get_metrics(request: Request = None):
    """Получение метрик"""
    path = "/metrics"
    return await forward_request('monitoring', path, 'GET', request)

@app.get("/api/v1/monitoring/alerts")
@handle_service_error
async def get_alerts(request: Request = None):
    """Получение алертов"""
    path = "/alerts"
    return await forward_request('monitoring', path, 'GET', request)

@app.get("/api/v1/monitoring/dashboard")
@handle_service_error
async def get_dashboard(request: Request = None):
    """Получение данных для дашборда"""
    path = "/dashboard"
    return await forward_request('monitoring', path, 'GET', request)

# ============================================================================
# Эндпоинты для синхронизации (Data Service)
# ============================================================================

@app.post("/api/v1/sync/ozon")
@handle_service_error
async def sync_with_ozon(request: Request = None):
    """Синхронизация с Ozon API"""
    path = "/sync/ozon"
    return await forward_request('data', path, 'POST', request)

# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка здоровья Gateway"""
    return {
        "service": "gateway",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": config['version'],
        "services": list(SERVICES.keys())
    }

# ============================================================================
# Middleware для логирования
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирует все запросы"""
    start_time = datetime.now()
    
    # Получаем IP адрес клиента
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
    
    response = await call_next(request)
    
    # Рассчитываем время выполнения
    process_time = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"Response: {response.status_code} in {process_time:.3f}s")
    
    # Добавляем заголовки
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Service"] = "gateway"
    
    return response

# ============================================================================
# Обработка ошибок
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    
    return ErrorResponse(
        success=False,
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        details={"path": str(request.url.path)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик общих исключений"""
    logger.error(f"General Exception: {exc}")
    
    return ErrorResponse(
        success=False,
        error_code="INTERNAL_ERROR",
        message="Internal server error",
        details={"path": str(request.url.path)}
    )

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=config['log_level'].lower()
    ) 