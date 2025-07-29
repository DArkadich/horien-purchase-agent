"""
Monitoring Service - мониторинг здоровья API и метрики
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx
import json
import psutil

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    HealthCheck, MetricsData, AlertData, DashboardData,
    BaseResponse, ErrorResponse
)
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient,
    DatabaseClient, handle_service_error, ServiceException
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('monitoring-service', config['log_level'])

# Инициализация клиентов
redis_client = RedisClient(config['redis_url'])
rabbitmq_client = RabbitMQClient(config['rabbitmq_url'])
db_client = DatabaseClient(config['postgres_url'])

# Конфигурация сервисов для мониторинга
SERVICES = {
    'gateway': 'http://gateway:8000/health',
    'data-service': 'http://data-service:8001/health',
    'forecast-service': 'http://forecast-service:8002/health',
    'notification-service': 'http://notification-service:8003/health',
    'storage-service': 'http://storage-service:8005/health'
}

# ============================================================================
# FastAPI приложение
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    # Startup
    logger.info("Monitoring Service запускается...")
    yield
    # Shutdown
    logger.info("Monitoring Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="Monitoring Service",
    description="Сервис для мониторинга здоровья API и сбора метрик",
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
# Класс для проверки здоровья сервисов
# ============================================================================

class HealthChecker:
    """Класс для проверки здоровья сервисов"""

    def __init__(self):
        self.timeout = 5.0

    async def check_service_health(self, service_name: str, health_url: str) -> Dict[str, Any]:
        """Проверяет здоровье конкретного сервиса"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                start_time = datetime.now()
                response = await client.get(health_url)
                response_time = (datetime.now() - start_time).total_seconds()

                if response.status_code == 200:
                    health_data = response.json()
                    return {
                        'service': service_name,
                        'status': 'healthy',
                        'response_time': response_time,
                        'details': health_data,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'service': service_name,
                        'status': 'unhealthy',
                        'response_time': response_time,
                        'error': f"HTTP {response.status_code}",
                        'timestamp': datetime.now().isoformat()
                    }

        except httpx.TimeoutException:
            return {
                'service': service_name,
                'status': 'timeout',
                'response_time': self.timeout,
                'error': 'Request timeout',
                'timestamp': datetime.now().isoformat()
            }
        except httpx.ConnectError:
            return {
                'service': service_name,
                'status': 'unreachable',
                'response_time': 0,
                'error': 'Connection failed',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'service': service_name,
                'status': 'error',
                'response_time': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def check_all_services(self) -> List[Dict[str, Any]]:
        """Проверяет здоровье всех сервисов"""
        logger.info("Проверка здоровья всех сервисов...")

        health_results = []
        for service_name, health_url in SERVICES.items():
            result = await self.check_service_health(service_name, health_url)
            health_results.append(result)

        # Определяем общий статус системы
        healthy_count = len([r for r in health_results if r['status'] == 'healthy'])
        total_count = len(health_results)

        overall_status = 'healthy' if healthy_count == total_count else 'degraded'
        if healthy_count == 0:
            overall_status = 'critical'

        logger.info(f"Статус системы: {overall_status} ({healthy_count}/{total_count} сервисов здоровы)")

        return health_results

# ============================================================================
# Класс для сбора метрик
# ============================================================================

class MetricsCollector:
    """Класс для сбора метрик производительности"""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.metrics_key = "monitoring:metrics"

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Собирает системные метрики"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used
            memory_total = memory.total

            # Disk
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used = disk.used
            disk_total = disk.total

            # Network
            network = psutil.net_io_counters()
            bytes_sent = network.bytes_sent
            bytes_recv = network.bytes_recv

            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'percent': memory_percent,
                    'used': memory_used,
                    'total': memory_total,
                    'available': memory.available
                },
                'disk': {
                    'percent': disk_percent,
                    'used': disk_used,
                    'total': disk_total,
                    'free': disk.free
                },
                'network': {
                    'bytes_sent': bytes_sent,
                    'bytes_recv': bytes_recv
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка сбора системных метрик: {e}")
            return {}

    def collect_api_metrics(self) -> Dict[str, Any]:
        """Собирает метрики API"""
        try:
            # Получаем метрики из Redis
            metrics_data = self.redis_client.get(self.metrics_key)
            if metrics_data:
                return json.loads(metrics_data)
            return {}
        except Exception as e:
            logger.error(f"Ошибка сбора метрик API: {e}")
            return {}

    def save_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Сохраняет метрики"""
        try:
            self.redis_client.set(
                self.metrics_key,
                json.dumps(metrics),
                ttl=3600  # 1 час
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик: {e}")
            return False

    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получает историю метрик"""
        try:
            # В реальной системе здесь будет запрос к БД
            # Пока возвращаем пустой список
            return []
        except Exception as e:
            logger.error(f"Ошибка получения истории метрик: {e}")
            return []

# ============================================================================
# Класс для управления алертами
# ============================================================================

class AlertManager:
    """Класс для управления алертами"""

    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client
        self.alert_thresholds = {
            'cpu_high': 80.0,
            'memory_high': 85.0,
            'disk_high': 90.0,
            'response_time_high': 2.0,
            'error_rate_high': 5.0
        }

    def check_alerts(self, health_data: List[Dict[str, Any]], 
                    system_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Проверяет условия для алертов"""
        alerts = []

        # Проверяем здоровье сервисов
        unhealthy_services = [s for s in health_data if s['status'] != 'healthy']
        if unhealthy_services:
            alerts.append({
                'type': 'SERVICE_UNHEALTHY',
                'severity': 'HIGH',
                'message': f"Неисправны сервисы: {[s['service'] for s in unhealthy_services]}",
                'details': unhealthy_services,
                'timestamp': datetime.now().isoformat()
            })

        # Проверяем системные метрики
        if system_metrics:
            cpu_percent = system_metrics.get('cpu', {}).get('percent', 0)
            if cpu_percent > self.alert_thresholds['cpu_high']:
                alerts.append({
                    'type': 'CPU_HIGH',
                    'severity': 'MEDIUM',
                    'message': f"Высокая загрузка CPU: {cpu_percent}%",
                    'details': {'cpu_percent': cpu_percent},
                    'timestamp': datetime.now().isoformat()
                })

            memory_percent = system_metrics.get('memory', {}).get('percent', 0)
            if memory_percent > self.alert_thresholds['memory_high']:
                alerts.append({
                    'type': 'MEMORY_HIGH',
                    'severity': 'MEDIUM',
                    'message': f"Высокое использование памяти: {memory_percent}%",
                    'details': {'memory_percent': memory_percent},
                    'timestamp': datetime.now().isoformat()
                })

            disk_percent = system_metrics.get('disk', {}).get('percent', 0)
            if disk_percent > self.alert_thresholds['disk_high']:
                alerts.append({
                    'type': 'DISK_HIGH',
                    'severity': 'HIGH',
                    'message': f"Высокое использование диска: {disk_percent}%",
                    'details': {'disk_percent': disk_percent},
                    'timestamp': datetime.now().isoformat()
                })

        return alerts

    def save_alert(self, alert: Dict[str, Any]) -> bool:
        """Сохраняет алерт в БД"""
        try:
            query = """
                INSERT INTO alerts 
                (alert_type, severity, message, details, created_at)
                VALUES (:alert_type, :severity, :message, :details, :created_at)
            """
            
            params = {
                'alert_type': alert['type'],
                'severity': alert['severity'],
                'message': alert['message'],
                'details': json.dumps(alert['details']),
                'created_at': alert['timestamp']
            }
            
            self.db_client.execute_query(query, params)
            logger.info(f"Алерт сохранен: {alert['type']}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения алерта: {e}")
            return False

    def get_active_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получает активные алерты"""
        try:
            query = """
                SELECT id, alert_type, severity, message, details, created_at
                FROM alerts
                WHERE created_at >= :start_date
                ORDER BY created_at DESC
            """
            
            start_date = (datetime.now() - timedelta(hours=hours)).isoformat()
            result = self.db_client.execute_query(query, {'start_date': start_date})
            
            # Парсим details из JSON
            for alert in result:
                if alert.get('details'):
                    try:
                        alert['details'] = json.loads(alert['details'])
                    except:
                        pass
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []

# ============================================================================
# Класс для дашборда
# ============================================================================

class DashboardManager:
    """Класс для управления данными дашборда"""

    def __init__(self, redis_client: RedisClient, db_client: DatabaseClient):
        self.redis_client = redis_client
        self.db_client = db_client

    def generate_dashboard_data(self, health_data: List[Dict[str, Any]], 
                              system_metrics: Dict[str, Any],
                              alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерирует данные для дашборда"""
        
        # Статистика здоровья сервисов
        total_services = len(health_data)
        healthy_services = len([s for s in health_data if s['status'] == 'healthy'])
        unhealthy_services = total_services - healthy_services

        # Статистика алертов
        high_severity_alerts = len([a for a in alerts if a['severity'] == 'HIGH'])
        medium_severity_alerts = len([a for a in alerts if a['severity'] == 'MEDIUM'])
        low_severity_alerts = len([a for a in alerts if a['severity'] == 'LOW'])

        # Системные метрики
        system_summary = {}
        if system_metrics:
            system_summary = {
                'cpu_percent': system_metrics.get('cpu', {}).get('percent', 0),
                'memory_percent': system_metrics.get('memory', {}).get('percent', 0),
                'disk_percent': system_metrics.get('disk', {}).get('percent', 0)
            }

        dashboard_data = {
            'overview': {
                'total_services': total_services,
                'healthy_services': healthy_services,
                'unhealthy_services': unhealthy_services,
                'health_percentage': (healthy_services / total_services * 100) if total_services > 0 else 0
            },
            'alerts': {
                'total_alerts': len(alerts),
                'high_severity': high_severity_alerts,
                'medium_severity': medium_severity_alerts,
                'low_severity': low_severity_alerts
            },
            'system': system_summary,
            'services': health_data,
            'recent_alerts': alerts[:10],  # Последние 10 алертов
            'timestamp': datetime.now().isoformat()
        }

        return dashboard_data

    def save_dashboard_data(self, dashboard_data: Dict[str, Any]) -> bool:
        """Сохраняет данные дашборда"""
        try:
            self.redis_client.set(
                'monitoring:dashboard',
                json.dumps(dashboard_data),
                ttl=300  # 5 минут
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных дашборда: {e}")
            return False

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Получает данные дашборда"""
        try:
            data = self.redis_client.get('monitoring:dashboard')
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Ошибка получения данных дашборда: {e}")
            return {}

# ============================================================================
# Инициализация компонентов
# ============================================================================

health_checker = HealthChecker()
metrics_collector = MetricsCollector(redis_client)
alert_manager = AlertManager(db_client)
dashboard_manager = DashboardManager(redis_client, db_client)

# ============================================================================
# Эндпоинты
# ============================================================================

@app.get("/health")
@handle_service_error
async def health_check():
    """Проверка здоровья сервиса мониторинга"""
    return {
        "service": "monitoring-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": config['version']
    }

@app.get("/health/all")
@handle_service_error
async def check_all_services():
    """Проверка здоровья всех сервисов"""
    logger.info("Запрос на проверку здоровья всех сервисов")
    
    health_results = await health_checker.check_all_services()
    
    # Сохраняем результаты
    redis_client.set(
        'monitoring:health_check',
        json.dumps(health_results),
        ttl=300  # 5 минут
    )
    
    return {
        'success': True,
        'services': health_results,
        'timestamp': datetime.now().isoformat()
    }

@app.get("/health/{service_name}")
@handle_service_error
async def check_service_health(service_name: str):
    """Проверка здоровья конкретного сервиса"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    health_url = SERVICES[service_name]
    result = await health_checker.check_service_health(service_name, health_url)
    
    return result

@app.get("/metrics")
@handle_service_error
async def get_metrics():
    """Получение метрик"""
    logger.info("Запрос метрик")

    # Собираем системные метрики
    system_metrics = metrics_collector.collect_system_metrics()
    
    # Собираем метрики API
    api_metrics = metrics_collector.collect_api_metrics()
    
    # Объединяем метрики
    all_metrics = {
        'system': system_metrics,
        'api': api_metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    # Сохраняем метрики
    metrics_collector.save_metrics(all_metrics)
    
    return all_metrics

@app.get("/metrics/history")
@handle_service_error
async def get_metrics_history(hours: int = 24):
    """Получение истории метрик"""
    logger.info(f"Запрос истории метрик за {hours} часов")
    
    history = metrics_collector.get_metrics_history(hours)
    
    return {
        'success': True,
        'history': history,
        'hours': hours
    }

@app.get("/alerts")
@handle_service_error
async def get_alerts(hours: int = 24):
    """Получение алертов"""
    logger.info(f"Запрос алертов за {hours} часов")
    
    alerts = alert_manager.get_active_alerts(hours)
    
    return {
        'success': True,
        'alerts': alerts,
        'count': len(alerts)
    }

@app.post("/alerts/check")
@handle_service_error
async def check_alerts(background_tasks: BackgroundTasks):
    """Проверка условий для алертов"""
    logger.info("Запрос на проверку алертов")
    
    # Получаем данные о здоровье сервисов
    health_data = await health_checker.check_all_services()
    
    # Получаем системные метрики
    system_metrics = metrics_collector.collect_system_metrics()
    
    # Проверяем алерты
    alerts = alert_manager.check_alerts(health_data, system_metrics)
    
    # Сохраняем алерты
    for alert in alerts:
        background_tasks.add_task(alert_manager.save_alert, alert)
    
    # Отправляем уведомления о критических алертах
    critical_alerts = [a for a in alerts if a['severity'] == 'HIGH']
    if critical_alerts:
        notification_event = {
            'event_type': 'critical_alert',
            'service': 'monitoring-service',
            'data': {
                'alerts': critical_alerts,
                'timestamp': datetime.now().isoformat()
            }
        }
        rabbitmq_client.publish_message('notifications.send', notification_event)
    
    return {
        'success': True,
        'alerts_found': len(alerts),
        'critical_alerts': len(critical_alerts),
        'alerts': alerts
    }

@app.get("/dashboard")
@handle_service_error
async def get_dashboard():
    """Получение данных для дашборда"""
    logger.info("Запрос данных дашборда")
    
    # Получаем данные о здоровье сервисов
    health_data = await health_checker.check_all_services()
    
    # Получаем системные метрики
    system_metrics = metrics_collector.collect_system_metrics()
    
    # Получаем алерты
    alerts = alert_manager.get_active_alerts(1)  # За последний час
    
    # Генерируем данные дашборда
    dashboard_data = dashboard_manager.generate_dashboard_data(
        health_data, system_metrics, alerts
    )
    
    # Сохраняем данные
    dashboard_manager.save_dashboard_data(dashboard_data)
    
    return dashboard_data

@app.get("/dashboard/cached")
@handle_service_error
async def get_cached_dashboard():
    """Получение кэшированных данных дашборда"""
    logger.info("Запрос кэшированных данных дашборда")
    
    dashboard_data = dashboard_manager.get_dashboard_data()
    
    if not dashboard_data:
        # Если кэш пуст, генерируем новые данные
        return await get_dashboard()
    
    return dashboard_data

@app.post("/metrics/collect")
@handle_service_error
async def collect_metrics(background_tasks: BackgroundTasks):
    """Принудительный сбор метрик"""
    logger.info("Запрос на принудительный сбор метрик")
    
    # Собираем системные метрики
    system_metrics = metrics_collector.collect_system_metrics()
    
    # Собираем метрики API
    api_metrics = metrics_collector.collect_api_metrics()
    
    # Объединяем метрики
    all_metrics = {
        'system': system_metrics,
        'api': api_metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    # Сохраняем метрики
    background_tasks.add_task(metrics_collector.save_metrics, all_metrics)
    
    # Отправляем событие о сборе метрик
    event = {
        'event_type': 'metrics_collected',
        'service': 'monitoring-service',
        'data': {
            'metrics_count': len(all_metrics),
            'timestamp': datetime.now().isoformat()
        }
    }
    
    rabbitmq_client.publish_message('monitoring.metrics', event)
    
    return {
        'success': True,
        'message': 'Метрики собраны и сохранены',
        'metrics': all_metrics
    }

@app.get("/status")
@handle_service_error
async def get_system_status():
    """Получение общего статуса системы"""
    logger.info("Запрос общего статуса системы")
    
    # Получаем данные о здоровье сервисов
    health_data = await health_checker.check_all_services()
    
    # Определяем общий статус
    healthy_count = len([s for s in health_data if s['status'] == 'healthy'])
    total_count = len(health_data)
    
    if healthy_count == total_count:
        overall_status = 'healthy'
    elif healthy_count == 0:
        overall_status = 'critical'
    else:
        overall_status = 'degraded'
    
    # Получаем системные метрики
    system_metrics = metrics_collector.collect_system_metrics()
    
    # Получаем активные алерты
    alerts = alert_manager.get_active_alerts(1)
    critical_alerts = len([a for a in alerts if a['severity'] == 'HIGH'])
    
    return {
        'overall_status': overall_status,
        'healthy_services': healthy_count,
        'total_services': total_count,
        'system_metrics': system_metrics,
        'active_alerts': len(alerts),
        'critical_alerts': critical_alerts,
        'timestamp': datetime.now().isoformat()
    }

# ============================================================================
# Фоновые задачи
# ============================================================================

async def periodic_health_check():
    """Периодическая проверка здоровья сервисов"""
    try:
        health_data = await health_checker.check_all_services()
        
        # Сохраняем результаты
        redis_client.set(
            'monitoring:health_check',
            json.dumps(health_data),
            ttl=300
        )
        
        # Проверяем алерты
        system_metrics = metrics_collector.collect_system_metrics()
        alerts = alert_manager.check_alerts(health_data, system_metrics)
        
        # Сохраняем алерты
        for alert in alerts:
            alert_manager.save_alert(alert)
        
        logger.info(f"Периодическая проверка завершена: {len(health_data)} сервисов, {len(alerts)} алертов")
        
    except Exception as e:
        logger.error(f"Ошибка периодической проверки здоровья: {e}")

async def periodic_metrics_collection():
    """Периодический сбор метрик"""
    try:
        system_metrics = metrics_collector.collect_system_metrics()
        api_metrics = metrics_collector.collect_api_metrics()
        
        all_metrics = {
            'system': system_metrics,
            'api': api_metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        metrics_collector.save_metrics(all_metrics)
        
        logger.info("Периодический сбор метрик завершен")
        
    except Exception as e:
        logger.error(f"Ошибка периодического сбора метрик: {e}")

# ============================================================================
# Обработчик событий из очереди
# ============================================================================

def handle_monitoring_event(ch, method, properties, body):
    """Обработчик событий из очереди"""
    try:
        event = json.loads(body)
        event_type = event.get('event_type')
        
        logger.info(f"Получено событие мониторинга: {event_type}")
        
        if event_type == 'api_request':
            # Обработка метрики API запроса
            data = event.get('data', {})
            logger.info(f"API запрос: {data.get('method')} {data.get('path')} -> {data.get('status_code')}")
            
        elif event_type == 'service_error':
            # Обработка ошибки сервиса
            data = event.get('data', {})
            logger.error(f"Ошибка сервиса: {data.get('service')} - {data.get('error')}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки события мониторинга: {e}")

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level=config['log_level'].lower()
    ) 