"""
Notification Service - отправка уведомлений
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

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    NotificationRequest, NotificationResponse, NotificationHistory,
    SubscriptionRequest, SubscriptionResponse, TemplateRequest,
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
logger = setup_logging('notification-service', config['log_level'])

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
    logger.info("Notification Service запускается...")
    yield
    # Shutdown
    logger.info("Notification Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="Notification Service",
    description="Сервис для отправки уведомлений в Telegram",
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
# Класс для работы с Telegram
# ============================================================================

class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Отправляет сообщение в Telegram"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": parse_mode
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        logger.info("Сообщение успешно отправлено в Telegram")
                        return True
                    else:
                        logger.error(f"Ошибка Telegram API: {result}")
                        return False
                else:
                    logger.error(f"Ошибка HTTP при отправке в Telegram: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке в Telegram: {e}")
            return False

    async def send_photo(self, photo_url: str, caption: str = "") -> bool:
        """Отправляет фото в Telegram"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sendPhoto",
                    json={
                        "chat_id": self.chat_id,
                        "photo": photo_url,
                        "caption": caption,
                        "parse_mode": "Markdown"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        logger.info("Фото успешно отправлено в Telegram")
                        return True
                    else:
                        logger.error(f"Ошибка Telegram API: {result}")
                        return False
                else:
                    logger.error(f"Ошибка HTTP при отправке фото: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке фото в Telegram: {e}")
            return False

# Инициализация Telegram уведомлений
telegram_notifier = TelegramNotifier(
    config.get('telegram_bot_token', ''),
    config.get('telegram_chat_id', '')
)

# ============================================================================
# Класс для управления шаблонами
# ============================================================================

class TemplateManager:
    """Класс для управления шаблонами сообщений"""

    def __init__(self):
        self.templates = {
            'forecast_alert': {
                'title': '🛒 Алерт по прогнозу закупок',
                'template': """
{alert_type} *{title}*

📊 *Статистика:*
• Всего позиций: {total_items}
• Требуют закупки: {needs_purchase}
• Критических: {critical_items}
• Общее количество: {total_quantity} шт

⏰ *Время:* {timestamp}
                """.strip()
            },
            'stock_alert': {
                'title': '📦 Алерт по остаткам',
                'template': """
{alert_type} *{title}*

📦 *Статистика остатков:*
• Низкий остаток (< 10): {low_stock}
• Средний остаток (10-50): {medium_stock}
• Высокий остаток (> 50): {high_stock}

⏰ *Время:* {timestamp}
                """.strip()
            },
            'system_alert': {
                'title': '🔧 Системное уведомление',
                'template': """
{alert_type} *{title}*

📝 *Сообщение:* {message}

🔗 *Действие:* {action}

⏰ *Время:* {timestamp}
                """.strip()
            },
            'sync_completed': {
                'title': '✅ Синхронизация завершена',
                'template': """
✅ *Синхронизация с Ozon API завершена*

📊 *Результаты:*
• Обработано товаров: {processed_items}
• Обновлено остатков: {updated_stocks}
• Время выполнения: {duration}

⏰ *Время:* {timestamp}
                """.strip()
            },
            'error_alert': {
                'title': '❌ Ошибка системы',
                'template': """
❌ *{title}*

🚨 *Ошибка:* {error_message}

📍 *Место:* {location}
🔧 *Действие:* {action}

⏰ *Время:* {timestamp}
                """.strip()
            }
        }

    def get_template(self, template_name: str) -> Optional[Dict[str, str]]:
        """Получает шаблон по имени"""
        return self.templates.get(template_name)

    def format_message(self, template_name: str, **kwargs) -> str:
        """Форматирует сообщение по шаблону"""
        template = self.get_template(template_name)
        if not template:
            return f"Неизвестный шаблон: {template_name}"
        
        try:
            return template['template'].format(**kwargs)
        except KeyError as e:
            logger.error(f"Ошибка форматирования шаблона {template_name}: {e}")
            return f"Ошибка форматирования шаблона: {e}"

    def add_template(self, name: str, title: str, template: str) -> bool:
        """Добавляет новый шаблон"""
        try:
            self.templates[name] = {
                'title': title,
                'template': template
            }
            logger.info(f"Добавлен новый шаблон: {name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления шаблона: {e}")
            return False

    def list_templates(self) -> List[Dict[str, str]]:
        """Возвращает список всех шаблонов"""
        return [
            {'name': name, 'title': template['title']}
            for name, template in self.templates.items()
        ]

# Инициализация менеджера шаблонов
template_manager = TemplateManager()

# ============================================================================
# Класс для управления подписками
# ============================================================================

class SubscriptionManager:
    """Класс для управления подписками на уведомления"""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.subscription_key = "notifications:subscriptions"

    def add_subscription(self, user_id: str, notification_types: List[str]) -> bool:
        """Добавляет подписку пользователя"""
        try:
            subscriptions = self.get_subscriptions()
            subscriptions[user_id] = {
                'notification_types': notification_types,
                'created_at': datetime.now().isoformat(),
                'active': True
            }
            
            self.redis_client.set(
                self.subscription_key,
                json.dumps(subscriptions),
                ttl=86400 * 30  # 30 дней
            )
            
            logger.info(f"Добавлена подписка для пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления подписки: {e}")
            return False

    def remove_subscription(self, user_id: str) -> bool:
        """Удаляет подписку пользователя"""
        try:
            subscriptions = self.get_subscriptions()
            if user_id in subscriptions:
                del subscriptions[user_id]
                
                self.redis_client.set(
                    self.subscription_key,
                    json.dumps(subscriptions),
                    ttl=86400 * 30
                )
                
                logger.info(f"Удалена подписка для пользователя {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления подписки: {e}")
            return False

    def get_subscriptions(self) -> Dict[str, Any]:
        """Получает все подписки"""
        try:
            data = self.redis_client.get(self.subscription_key)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Ошибка получения подписок: {e}")
            return {}

    def is_subscribed(self, user_id: str, notification_type: str) -> bool:
        """Проверяет, подписан ли пользователь на тип уведомлений"""
        subscriptions = self.get_subscriptions()
        user_sub = subscriptions.get(user_id, {})
        
        if not user_sub.get('active', False):
            return False
        
        return notification_type in user_sub.get('notification_types', [])

    def get_active_subscribers(self, notification_type: str) -> List[str]:
        """Получает список активных подписчиков на тип уведомлений"""
        subscriptions = self.get_subscriptions()
        subscribers = []
        
        for user_id, sub in subscriptions.items():
            if sub.get('active', False) and notification_type in sub.get('notification_types', []):
                subscribers.append(user_id)
        
        return subscribers

# ============================================================================
# Класс для истории уведомлений
# ============================================================================

class NotificationHistoryManager:
    """Класс для управления историей уведомлений"""

    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client

    def save_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Сохраняет уведомление в историю"""
        try:
            query = """
                INSERT INTO notification_history 
                (notification_type, recipient, message, status, created_at)
                VALUES (:notification_type, :recipient, :message, :status, :created_at)
            """
            
            params = {
                'notification_type': notification_data.get('type', 'unknown'),
                'recipient': notification_data.get('recipient', 'telegram'),
                'message': notification_data.get('message', ''),
                'status': notification_data.get('status', 'sent'),
                'created_at': datetime.now().isoformat()
            }
            
            self.db_client.execute_query(query, params)
            logger.info("Уведомление сохранено в историю")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения уведомления: {e}")
            return False

    def get_notification_history(self, limit: int = 100, 
                               notification_type: str = None) -> List[Dict[str, Any]]:
        """Получает историю уведомлений"""
        try:
            query = """
                SELECT id, notification_type, recipient, message, status, created_at
                FROM notification_history
            """
            params = {}
            
            if notification_type:
                query += " WHERE notification_type = :notification_type"
                params['notification_type'] = notification_type
            
            query += " ORDER BY created_at DESC LIMIT :limit"
            params['limit'] = limit
            
            result = self.db_client.execute_query(query, params)
            return result
        except Exception as e:
            logger.error(f"Ошибка получения истории уведомлений: {e}")
            return []

    def get_notification_stats(self) -> Dict[str, Any]:
        """Получает статистику уведомлений"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_notifications,
                    COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                    notification_type,
                    DATE(created_at) as date
                FROM notification_history
                WHERE created_at >= :start_date
                GROUP BY notification_type, DATE(created_at)
                ORDER BY date DESC
            """
            
            start_date = (datetime.now() - timedelta(days=30)).isoformat()
            result = self.db_client.execute_query(query, {'start_date': start_date})
            
            stats = {
                'total_notifications': 0,
                'sent_count': 0,
                'failed_count': 0,
                'by_type': {},
                'by_date': {}
            }
            
            for row in result:
                stats['total_notifications'] += row['total_notifications']
                stats['sent_count'] += row['sent_count']
                stats['failed_count'] += row['failed_count']
                
                # Статистика по типам
                if row['notification_type'] not in stats['by_type']:
                    stats['by_type'][row['notification_type']] = {
                        'total': 0,
                        'sent': 0,
                        'failed': 0
                    }
                
                stats['by_type'][row['notification_type']]['total'] += row['total_notifications']
                stats['by_type'][row['notification_type']]['sent'] += row['sent_count']
                stats['by_type'][row['notification_type']]['failed'] += row['failed_count']
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики уведомлений: {e}")
            return {}

# ============================================================================
# Эндпоинты
# ============================================================================

@app.post("/notifications/send", response_model=NotificationResponse)
@handle_service_error
async def send_notification(
    request: NotificationRequest,
    background_tasks: BackgroundTasks,
    redis_client: RedisClient = Depends(get_redis_client),
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Отправка уведомления"""
    logger.info(f"Запрос на отправку уведомления типа: {request.notification_type}")

    # Форматируем сообщение по шаблону
    if request.template_name:
        message = template_manager.format_message(
            request.template_name,
            **request.template_data
        )
    else:
        message = request.message

    # Отправляем уведомление
    success = await telegram_notifier.send_message(message)

    # Сохраняем в историю
    notification_data = {
        'type': request.notification_type,
        'recipient': 'telegram',
        'message': message,
        'status': 'sent' if success else 'failed'
    }

    background_tasks.add_task(
        save_notification_history,
        notification_data,
        redis_client
    )

    # Отправляем событие в очередь
    event = {
        'event_type': 'notification_sent',
        'service': 'notification-service',
        'data': {
            'notification_type': request.notification_type,
            'success': success,
            'timestamp': datetime.now().isoformat()
        }
    }

    rabbitmq_client.publish_message('notifications.events', event)

    return NotificationResponse(
        success=success,
        message="Уведомление отправлено" if success else "Ошибка отправки уведомления",
        notification_id=f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

@app.post("/notifications/send_photo")
@handle_service_error
async def send_photo_notification(
    photo_url: str,
    caption: str = "",
    background_tasks: BackgroundTasks = None,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Отправка фото-уведомления"""
    logger.info("Запрос на отправку фото-уведомления")

    success = await telegram_notifier.send_photo(photo_url, caption)

    # Отправляем событие в очередь
    event = {
        'event_type': 'photo_notification_sent',
        'service': 'notification-service',
        'data': {
            'photo_url': photo_url,
            'success': success,
            'timestamp': datetime.now().isoformat()
        }
    }

    rabbitmq_client.publish_message('notifications.events', event)

    return {
        'success': success,
        'message': "Фото отправлено" if success else "Ошибка отправки фото"
    }

@app.post("/subscriptions/add", response_model=SubscriptionResponse)
@handle_service_error
async def add_subscription(
    request: SubscriptionRequest,
    redis_client: RedisClient = Depends(get_redis_client)
):
    """Добавление подписки на уведомления"""
    logger.info(f"Запрос на добавление подписки для пользователя {request.user_id}")

    subscription_manager = SubscriptionManager(redis_client)
    success = subscription_manager.add_subscription(
        request.user_id,
        request.notification_types
    )

    return SubscriptionResponse(
        success=success,
        message="Подписка добавлена" if success else "Ошибка добавления подписки"
    )

@app.delete("/subscriptions/remove/{user_id}", response_model=SubscriptionResponse)
@handle_service_error
async def remove_subscription(
    user_id: str,
    redis_client: RedisClient = Depends(get_redis_client)
):
    """Удаление подписки на уведомления"""
    logger.info(f"Запрос на удаление подписки для пользователя {user_id}")

    subscription_manager = SubscriptionManager(redis_client)
    success = subscription_manager.remove_subscription(user_id)

    return SubscriptionResponse(
        success=success,
        message="Подписка удалена" if success else "Подписка не найдена"
    )

@app.get("/subscriptions/{user_id}")
@handle_service_error
async def get_user_subscription(
    user_id: str,
    redis_client: RedisClient = Depends(get_redis_client)
):
    """Получение подписки пользователя"""
    subscription_manager = SubscriptionManager(redis_client)
    subscriptions = subscription_manager.get_subscriptions()
    
    user_subscription = subscriptions.get(user_id, {})
    
    return {
        'user_id': user_id,
        'subscription': user_subscription,
        'active': user_subscription.get('active', False)
    }

@app.get("/subscriptions/active/{notification_type}")
@handle_service_error
async def get_active_subscribers(
    notification_type: str,
    redis_client: RedisClient = Depends(get_redis_client)
):
    """Получение активных подписчиков на тип уведомлений"""
    subscription_manager = SubscriptionManager(redis_client)
    subscribers = subscription_manager.get_active_subscribers(notification_type)
    
    return {
        'notification_type': notification_type,
        'subscribers': subscribers,
        'count': len(subscribers)
    }

@app.get("/templates")
@handle_service_error
async def get_templates():
    """Получение списка шаблонов"""
    templates = template_manager.list_templates()
    
    return {
        'templates': templates,
        'count': len(templates)
    }

@app.post("/templates/add")
@handle_service_error
async def add_template(request: TemplateRequest):
    """Добавление нового шаблона"""
    logger.info(f"Запрос на добавление шаблона: {request.name}")

    success = template_manager.add_template(
        request.name,
        request.title,
        request.template
    )

    return {
        'success': success,
        'message': "Шаблон добавлен" if success else "Ошибка добавления шаблона"
    }

@app.get("/history", response_model=NotificationHistory)
@handle_service_error
async def get_notification_history(
    limit: int = 100,
    notification_type: str = None,
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение истории уведомлений"""
    logger.info(f"Запрос истории уведомлений: limit={limit}, type={notification_type}")

    history_manager = NotificationHistoryManager(db_client)
    history = history_manager.get_notification_history(limit, notification_type)

    return NotificationHistory(
        success=True,
        notifications=history,
        total_count=len(history)
    )

@app.get("/history/stats")
@handle_service_error
async def get_notification_stats(
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение статистики уведомлений"""
    logger.info("Запрос статистики уведомлений")

    history_manager = NotificationHistoryManager(db_client)
    stats = history_manager.get_notification_stats()

    return {
        'success': True,
        'stats': stats
    }

@app.post("/notifications/broadcast")
@handle_service_error
async def broadcast_notification(
    notification_type: str,
    message: str,
    background_tasks: BackgroundTasks,
    redis_client: RedisClient = Depends(get_redis_client),
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Массовая рассылка уведомлений"""
    logger.info(f"Запрос на массовую рассылку типа: {notification_type}")

    subscription_manager = SubscriptionManager(redis_client)
    subscribers = subscription_manager.get_active_subscribers(notification_type)

    if not subscribers:
        return {
            'success': False,
            'message': "Нет активных подписчиков для данного типа уведомлений"
        }

    # Отправляем всем подписчикам
    success_count = 0
    for subscriber in subscribers:
        success = await telegram_notifier.send_message(message)
        if success:
            success_count += 1

    # Отправляем событие в очередь
    event = {
        'event_type': 'broadcast_completed',
        'service': 'notification-service',
        'data': {
            'notification_type': notification_type,
            'total_subscribers': len(subscribers),
            'success_count': success_count,
            'timestamp': datetime.now().isoformat()
        }
    }

    rabbitmq_client.publish_message('notifications.events', event)

    return {
        'success': True,
        'message': f"Рассылка завершена: {success_count}/{len(subscribers)} успешно"
    }

# ============================================================================
# Фоновые задачи
# ============================================================================

async def save_notification_history(
    notification_data: Dict[str, Any],
    redis_client: RedisClient
):
    """Сохранение уведомления в историю"""
    try:
        # Здесь можно добавить сохранение в БД
        # Пока просто логируем
        logger.info(f"Сохранение уведомления в историю: {notification_data['type']}")
    except Exception as e:
        logger.error(f"Ошибка сохранения уведомления в историю: {e}")

# ============================================================================
# Обработчик событий из очереди
# ============================================================================

def handle_notification_event(ch, method, properties, body):
    """Обработчик событий из очереди"""
    try:
        event = json.loads(body)
        event_type = event.get('event_type')
        
        logger.info(f"Получено событие: {event_type}")
        
        if event_type == 'forecast_alert':
            # Обработка алерта по прогнозу
            message = template_manager.format_message(
                'forecast_alert',
                **event.get('data', {})
            )
            telegram_notifier.send_message(message)
            
        elif event_type == 'stock_alert':
            # Обработка алерта по остаткам
            message = template_manager.format_message(
                'stock_alert',
                **event.get('data', {})
            )
            telegram_notifier.send_message(message)
            
        elif event_type == 'system_alert':
            # Обработка системного алерта
            message = template_manager.format_message(
                'system_alert',
                **event.get('data', {})
            )
            telegram_notifier.send_message(message)
            
    except Exception as e:
        logger.error(f"Ошибка обработки события: {e}")

# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "service": "notification-service",
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
        port=8003,
        reload=True,
        log_level=config['log_level'].lower()
    ) 