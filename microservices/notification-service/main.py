"""
Notification Service - отправка уведомлений
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import logging
import httpx
from typing import List, Dict, Any
from datetime import datetime

from shared.models import NotificationMessage
from shared.utils import (
    ServiceUtils, MetricsCollector, HealthChecker, 
    MessageQueue, timing_decorator
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Notification Service", version="1.0.0")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
metrics_collector = MetricsCollector("notification-service")
health_checker = HealthChecker("notification-service")
message_queue = MessageQueue("amqp://guest:guest@rabbitmq:5672/")

# Импорт из оригинального кода
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from telegram_notify import TelegramNotifier

# Инициализация Telegram уведомлений
telegram_notifier = TelegramNotifier()

# История уведомлений (в реальной системе это будет в БД)
notification_history = []

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    # Добавляем проверки здоровья
    health_checker.add_check("telegram", lambda: telegram_notifier is not None)
    health_checker.add_check("message_queue", lambda: message_queue is not None)

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    checks = health_checker.run_health_checks()
    overall_status = "healthy" if all(
        check["status"] == "healthy" for check in checks.values()
    ) else "unhealthy"
    
    return {
        "service": "notification-service",
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/metrics")
async def get_metrics():
    """Получает метрики сервиса"""
    return {
        "service": "notification-service",
        "metrics": metrics_collector.get_metrics(),
        "timestamp": datetime.now().isoformat()
    }

@timing_decorator(metrics_collector)
@app.post("/send")
async def send_notification(message: Dict[str, Any]):
    """Отправляет уведомление"""
    try:
        # Валидируем сообщение
        if "text" not in message:
            raise HTTPException(status_code=400, detail="Message must contain 'text' field")
        
        text = message["text"]
        level = message.get("level", "info")
        
        # Создаем объект уведомления
        notification = NotificationMessage(
            service="notification-service",
            message=text,
            level=level,
            metadata=message.get("metadata", {})
        )
        
        # Отправляем через Telegram
        success = await telegram_notifier.send_message(text)
        
        if success:
            # Сохраняем в историю
            notification_history.append({
                "id": ServiceUtils.generate_correlation_id(),
                "message": notification.dict(),
                "sent_at": datetime.now().isoformat(),
                "status": "sent"
            })
            
            # Отправляем событие об успешной отправке
            message_queue.publish_event(
                "notification_sent",
                {
                    "notification_id": notification_history[-1]["id"],
                    "level": level,
                    "timestamp": datetime.now().isoformat()
                },
                routing_key="notification_events"
            )
            
            metrics_collector.record_counter("notifications_sent", 1)
            logger.info(f"Уведомление отправлено: {text[:50]}...")
            
            return {
                "status": "sent",
                "notification_id": notification_history[-1]["id"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            metrics_collector.record_counter("notifications_failed", 1)
            raise HTTPException(status_code=500, detail="Failed to send notification")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        metrics_collector.record_counter("notifications_error", 1)
        
        # Отправляем событие об ошибке
        message_queue.publish_event(
            "notification_error",
            {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            routing_key="notification_events"
        )
        
        raise HTTPException(status_code=500, detail=f"Notification sending failed: {str(e)}")

@app.post("/send/batch")
async def send_batch_notifications(messages: List[Dict[str, Any]]):
    """Отправляет пакет уведомлений"""
    try:
        results = []
        
        for message in messages:
            try:
                result = await send_notification(message)
                results.append({
                    "message": message,
                    "status": "success",
                    "result": result
                })
            except Exception as e:
                results.append({
                    "message": message,
                    "status": "error",
                    "error": str(e)
                })
        
        success_count = len([r for r in results if r["status"] == "success"])
        error_count = len([r for r in results if r["status"] == "error"])
        
        metrics_collector.record_counter("batch_notifications_sent", success_count)
        metrics_collector.record_counter("batch_notifications_failed", error_count)
        
        return {
            "results": results,
            "summary": {
                "total": len(messages),
                "success": success_count,
                "errors": error_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка отправки пакета уведомлений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_notification_history(limit: int = 50):
    """Получает историю уведомлений"""
    return {
        "notifications": notification_history[-limit:] if notification_history else [],
        "total_count": len(notification_history),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/templates")
async def get_notification_templates():
    """Получает доступные шаблоны уведомлений"""
    templates = [
        {
            "name": "forecast_report",
            "description": "Отчет о прогнозе закупок",
            "template": "🛒 *Отчет о закупках*\n\n{content}",
            "variables": ["content"]
        },
        {
            "name": "api_health_alert",
            "description": "Алерт о здоровье API",
            "template": "🚨 *API Health Alert*\n\n{service}: {status}\n{details}",
            "variables": ["service", "status", "details"]
        },
        {
            "name": "data_refresh",
            "description": "Уведомление об обновлении данных",
            "template": "📊 *Data Refresh*\n\nОбновлено:\n- Товары: {products_count}\n- Остатки: {stocks_count}\n- Продажи: {sales_count}",
            "variables": ["products_count", "stocks_count", "sales_count"]
        }
    ]
    
    return {
        "templates": templates,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/templates/{template_name}")
async def send_template_notification(template_name: str, variables: Dict[str, Any]):
    """Отправляет уведомление по шаблону"""
    try:
        # Получаем шаблон
        templates_response = await get_notification_templates()
        template = next((t for t in templates_response["templates"] if t["name"] == template_name), None)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        # Проверяем наличие всех переменных
        missing_vars = [var for var in template["variables"] if var not in variables]
        if missing_vars:
            raise HTTPException(status_code=400, detail=f"Missing variables: {missing_vars}")
        
        # Формируем сообщение
        message_text = template["template"]
        for var_name, var_value in variables.items():
            message_text = message_text.replace(f"{{{var_name}}}", str(var_value))
        
        # Отправляем уведомление
        return await send_notification({
            "text": message_text,
            "level": "info",
            "metadata": {
                "template": template_name,
                "variables": variables
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления по шаблону: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/subscriptions")
async def get_subscriptions():
    """Получает список подписок"""
    # Заглушка для подписок
    return {
        "subscriptions": [
            {
                "id": "default",
                "name": "Default Subscription",
                "telegram_chat_id": "default",
                "enabled": True,
                "created_at": datetime.now().isoformat()
            }
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/subscriptions")
async def create_subscription(subscription: Dict[str, Any]):
    """Создает новую подписку"""
    # Заглушка для создания подписки
    return {
        "id": ServiceUtils.generate_correlation_id(),
        "subscription": subscription,
        "created_at": datetime.now().isoformat()
    }

@app.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """Удаляет подписку"""
    # Заглушка для удаления подписки
    return {
        "id": subscription_id,
        "deleted_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 