"""
Общие утилиты для микросервисов
"""

import os
import json
import logging
import redis
import pika
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# ============================================================================
# Конфигурация
# ============================================================================

def get_config() -> Dict[str, Any]:
    """Получение конфигурации из переменных окружения"""
    return {
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379'),
        'rabbitmq_url': os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/'),
        'postgres_url': os.getenv('POSTGRES_URL', 'postgresql://ozon_user:ozon_password@localhost:5432/ozon_microservices'),
        'service_name': os.getenv('SERVICE_NAME', 'unknown'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'version': os.getenv('VERSION', '1.0.0'),
    }

def setup_logging(service_name: str, log_level: str = 'INFO') -> logging.Logger:
    """Настройка логирования для сервиса"""
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# ============================================================================
# Redis утилиты
# ============================================================================

class RedisClient:
    """Клиент для работы с Redis"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client = None
        self._connect()
    
    def _connect(self):
        """Подключение к Redis"""
        try:
            self.client = redis.from_url(self.redis_url)
            self.client.ping()  # Проверка соединения
        except Exception as e:
            logging.error(f"Ошибка подключения к Redis: {e}")
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logging.error(f"Ошибка получения из Redis: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Установка значения в кэш"""
        if not self.client:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            return self.client.setex(key, ttl, serialized)
        except Exception as e:
            logging.error(f"Ошибка записи в Redis: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        if not self.client:
            return False
        
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logging.error(f"Ошибка удаления из Redis: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Проверка существования ключа"""
        if not self.client:
            return False
        
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logging.error(f"Ошибка проверки ключа в Redis: {e}")
            return False

# ============================================================================
# RabbitMQ утилиты
# ============================================================================

class RabbitMQClient:
    """Клиент для работы с RabbitMQ"""
    
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self._connect()
    
    def _connect(self):
        """Подключение к RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.rabbitmq_url)
            )
            self.channel = self.connection.channel()
        except Exception as e:
            logging.error(f"Ошибка подключения к RabbitMQ: {e}")
            self.connection = None
            self.channel = None
    
    def publish_message(self, queue: str, message: Dict[str, Any]) -> bool:
        """Публикация сообщения в очередь"""
        if not self.channel:
            return False
        
        try:
            self.channel.queue_declare(queue=queue, durable=True)
            self.channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Сохранять сообщения на диск
                )
            )
            return True
        except Exception as e:
            logging.error(f"Ошибка публикации в RabbitMQ: {e}")
            return False
    
    def consume_messages(self, queue: str, callback) -> bool:
        """Потребление сообщений из очереди"""
        if not self.channel:
            return False
        
        try:
            self.channel.queue_declare(queue=queue, durable=True)
            self.channel.basic_consume(
                queue=queue,
                on_message_callback=callback,
                auto_ack=True
            )
            self.channel.start_consuming()
            return True
        except Exception as e:
            logging.error(f"Ошибка потребления из RabbitMQ: {e}")
            return False
    
    def close(self):
        """Закрытие соединения"""
        if self.connection:
            self.connection.close()

# ============================================================================
# PostgreSQL утилиты
# ============================================================================

class DatabaseClient:
    """Клиент для работы с PostgreSQL"""
    
    def __init__(self, postgres_url: str):
        self.postgres_url = postgres_url
        self.engine = None
        self.SessionLocal = None
        self._connect()
    
    def _connect(self):
        """Подключение к PostgreSQL"""
        try:
            self.engine = create_engine(self.postgres_url)
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            # Проверка соединения
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            logging.error(f"Ошибка подключения к PostgreSQL: {e}")
            self.engine = None
            self.SessionLocal = None
    
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для сессии БД"""
        if not self.SessionLocal:
            raise Exception("База данных не подключена")
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Выполнение SQL запроса"""
        if not self.engine:
            return []
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row) for row in result]
        except Exception as e:
            logging.error(f"Ошибка выполнения запроса: {e}")
            return []

# ============================================================================
# Утилиты для работы с данными
# ============================================================================

def validate_data(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Валидация данных"""
    for field in required_fields:
        if field not in data or data[field] is None:
            return False
    return True

def clean_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Очистка данных от None значений"""
    return {k: v for k, v in data.items() if v is not None}

def format_datetime(dt: datetime) -> str:
    """Форматирование даты/времени"""
    return dt.isoformat()

def parse_datetime(dt_str: str) -> datetime:
    """Парсинг даты/времени"""
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

# ============================================================================
# Утилиты для мониторинга
# ============================================================================

def get_service_health(service_name: str, start_time: datetime) -> Dict[str, Any]:
    """Получение информации о здоровье сервиса"""
    import psutil
    
    uptime = (datetime.now() - start_time).total_seconds()
    memory_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent()
    
    return {
        'service': service_name,
        'status': 'healthy',
        'uptime': uptime,
        'memory_usage': memory_usage,
        'cpu_usage': cpu_usage,
        'timestamp': datetime.now().isoformat()
    }

def create_metric(endpoint: str, method: str, response_time: float, 
                  status_code: int, user_agent: str = None, 
                  ip_address: str = None) -> Dict[str, Any]:
    """Создание метрики API"""
    return {
        'endpoint': endpoint,
        'method': method,
        'response_time': response_time,
        'status_code': status_code,
        'user_agent': user_agent,
        'ip_address': ip_address,
        'timestamp': datetime.now().isoformat()
    }

# ============================================================================
# Утилиты для кэширования
# ============================================================================

def generate_cache_key(prefix: str, **kwargs) -> str:
    """Генерация ключа кэша"""
    key_parts = [prefix]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    return ":".join(key_parts)

def cache_result(redis_client: RedisClient, key: str, result: Any, 
                ttl: int = 3600) -> bool:
    """Кэширование результата"""
    return redis_client.set(key, result, ttl)

def get_cached_result(redis_client: RedisClient, key: str) -> Optional[Any]:
    """Получение кэшированного результата"""
    return redis_client.get(key)

# ============================================================================
# Утилиты для очередей
# ============================================================================

def create_event(event_type: str, service: str, data: Dict[str, Any], 
                correlation_id: str = None) -> Dict[str, Any]:
    """Создание события для очереди"""
    return {
        'event_type': event_type,
        'service': service,
        'data': data,
        'timestamp': datetime.now().isoformat(),
        'correlation_id': correlation_id
    }

def publish_event(rabbitmq_client: RabbitMQClient, queue: str, 
                 event: Dict[str, Any]) -> bool:
    """Публикация события в очередь"""
    return rabbitmq_client.publish_message(queue, event)

# ============================================================================
# Утилиты для ошибок
# ============================================================================

class ServiceException(Exception):
    """Базовое исключение для сервисов"""
    
    def __init__(self, message: str, error_code: str = None, 
                 details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

def handle_service_error(func):
    """Декоратор для обработки ошибок сервисов"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Ошибка в {func.__name__}: {e}")
            raise ServiceException(
                message=str(e),
                error_code="INTERNAL_ERROR",
                details={'function': func.__name__}
            )
    return wrapper 