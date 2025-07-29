"""
Monitoring Service - мониторинг здоровья API и метрики
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import logging
import httpx
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta

from shared.models import ServiceHealth, ServiceStatus, APIMetric
from shared.utils import (
    ServiceUtils, MetricsCollector, HealthChecker, 
    MessageQueue, timing_decorator
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Monitoring Service", version="1.0.0")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
metrics_collector = MetricsCollector("monitoring-service")
health_checker = HealthChecker("monitoring-service")
message_queue = MessageQueue("amqp://guest:guest@rabbitmq:5672/")

# HTTP клиент для проверки сервисов
http_client = httpx.AsyncClient(timeout=30.0)

# Импорт из оригинального кода
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from api_monitor import APIMonitor, APIMonitoringService
from api_metrics import APIMetricsCollector

# Инициализация компонентов мониторинга
api_monitor = APIMonitor()
api_metrics_collector = APIMetricsCollector()

# Список сервисов для мониторинга
SERVICES_TO_MONITOR = [
    {"name": "data-service", "url": "http://data-service:8001/health"},
    {"name": "forecast-service", "url": "http://forecast-service:8002/health"},
    {"name": "notification-service", "url": "http://notification-service:8003/health"},
    {"name": "storage-service", "url": "http://storage-service:8005/health"}
]

# История мониторинга
monitoring_history = []

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    # Добавляем проверки здоровья
    health_checker.add_check("api_monitor", lambda: api_monitor is not None)
    health_checker.add_check("api_metrics", lambda: api_metrics_collector is not None)
    health_checker.add_check("message_queue", lambda: message_queue is not None)

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    checks = health_checker.run_health_checks()
    overall_status = "healthy" if all(
        check["status"] == "healthy" for check in checks.values()
    ) else "unhealthy"
    
    return {
        "service": "monitoring-service",
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/metrics")
async def get_metrics():
    """Получает метрики сервиса"""
    return {
        "service": "monitoring-service",
        "metrics": metrics_collector.get_metrics(),
        "timestamp": datetime.now().isoformat()
    }

@timing_decorator(metrics_collector)
@app.get("/health/all")
async def check_all_services_health():
    """Проверяет здоровье всех сервисов"""
    try:
        health_results = {}
        
        for service in SERVICES_TO_MONITOR:
            try:
                start_time = datetime.now()
                response = await http_client.get(service["url"])
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status_code == 200:
                    health_data = response.json()
                    health_results[service["name"]] = {
                        "status": "healthy",
                        "response_time": duration,
                        "details": health_data,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    health_results[service["name"]] = {
                        "status": "unhealthy",
                        "response_time": duration,
                        "error": f"HTTP {response.status_code}",
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except Exception as e:
                health_results[service["name"]] = {
                    "status": "down",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        # Сохраняем в историю
        monitoring_history.append({
            "timestamp": datetime.now().isoformat(),
            "results": health_results
        })
        
        # Отправляем событие о проверке здоровья
        message_queue.publish_event(
            "health_check_completed",
            {
                "results": health_results,
                "timestamp": datetime.now().isoformat()
            },
            routing_key="monitoring_events"
        )
        
        metrics_collector.record_counter("health_checks_completed", 1)
        
        return {
            "services": health_results,
            "summary": {
                "total": len(SERVICES_TO_MONITOR),
                "healthy": len([s for s in health_results.values() if s["status"] == "healthy"]),
                "unhealthy": len([s for s in health_results.values() if s["status"] == "unhealthy"]),
                "down": len([s for s in health_results.values() if s["status"] == "down"])
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья сервисов: {e}")
        metrics_collector.record_counter("health_check_error", 1)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def get_api_health():
    """Получает здоровье внешних API"""
    try:
        # Проверяем Ozon API
        ozon_api_health = await check_ozon_api_health()
        
        return {
            "external_apis": {
                "ozon_api": ozon_api_health
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения здоровья API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def check_ozon_api_health():
    """Проверяет здоровье Ozon API"""
    try:
        # Импортируем OzonAPI для проверки
        from ozon_api import OzonAPI
        
        ozon_api = OzonAPI()
        start_time = datetime.now()
        
        # Пытаемся получить товары
        products = ozon_api.get_products()
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        if products:
            return {
                "status": "healthy",
                "response_time": duration,
                "products_count": len(products),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unhealthy",
                "response_time": duration,
                "error": "No products returned",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/metrics/api")
async def get_api_metrics():
    """Получает метрики API"""
    try:
        # Получаем сводку метрик из APIMetricsCollector
        summary = api_metrics_collector.get_metrics_summary(hours=24)
        
        return {
            "api_metrics": summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/performance")
async def get_performance_metrics():
    """Получает метрики производительности"""
    try:
        # Получаем тренды производительности
        trends = api_metrics_collector.get_performance_trends(hours=24)
        
        return {
            "performance_trends": trends,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик производительности: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts():
    """Получает активные алерты"""
    try:
        # Получаем алерты из APIMonitor
        alerts = api_monitor.get_recent_incidents(hours=24)
        
        return {
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения алертов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/resolve/{alert_id}")
async def resolve_alert(alert_id: str):
    """Разрешает алерт"""
    try:
        # Заглушка для разрешения алерта
        return {
            "alert_id": alert_id,
            "status": "resolved",
            "resolved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка разрешения алерта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/health")
async def generate_health_report():
    """Генерирует отчет о здоровье"""
    try:
        # Получаем данные о здоровье
        health_data = await check_all_services_health()
        api_health = await get_api_health()
        
        # Формируем отчет
        report = {
            "summary": {
                "services_health": health_data["summary"],
                "external_apis": {
                    "ozon_api": api_health["external_apis"]["ozon_api"]["status"]
                }
            },
            "details": {
                "services": health_data["services"],
                "external_apis": api_health["external_apis"]
            },
            "generated_at": datetime.now().isoformat()
        }
        
        # Отправляем событие о генерации отчета
        message_queue.publish_event(
            "health_report_generated",
            {
                "report": report,
                "timestamp": datetime.now().isoformat()
            },
            routing_key="monitoring_events"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета о здоровье: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/performance")
async def generate_performance_report():
    """Генерирует отчет о производительности"""
    try:
        # Получаем метрики производительности
        performance_metrics = await get_performance_metrics()
        api_metrics = await get_api_metrics()
        
        # Формируем отчет
        report = {
            "performance_metrics": performance_metrics,
            "api_metrics": api_metrics,
            "generated_at": datetime.now().isoformat()
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета о производительности: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_monitoring_history(limit: int = 50):
    """Получает историю мониторинга"""
    return {
        "history": monitoring_history[-limit:] if monitoring_history else [],
        "total_count": len(monitoring_history),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/monitoring/start")
async def start_monitoring():
    """Запускает мониторинг"""
    try:
        # Запускаем фоновый мониторинг
        asyncio.create_task(background_monitoring())
        
        return {
            "status": "started",
            "message": "Monitoring started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка запуска мониторинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def background_monitoring():
    """Фоновый мониторинг"""
    while True:
        try:
            # Проверяем здоровье сервисов
            await check_all_services_health()
            
            # Проверяем здоровье API
            await get_api_health()
            
            # Ждем 5 минут
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Ошибка фонового мониторинга: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004) 