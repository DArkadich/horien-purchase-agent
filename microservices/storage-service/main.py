"""
Storage Service - управление Google Sheets и файлами
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import logging
import httpx
from typing import List, Dict, Any
from datetime import datetime

from shared.models import PurchaseReport
from shared.utils import (
    ServiceUtils, MetricsCollector, HealthChecker, 
    MessageQueue, timing_decorator
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Storage Service", version="1.0.0")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
metrics_collector = MetricsCollector("storage-service")
health_checker = HealthChecker("storage-service")
message_queue = MessageQueue("amqp://guest:guest@rabbitmq:5672/")

# Импорт из оригинального кода
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from sheets import GoogleSheets

# Инициализация Google Sheets
sheets_manager = GoogleSheets()

# История операций с файлами
storage_history = []

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    # Добавляем проверки здоровья
    health_checker.add_check("sheets_manager", lambda: sheets_manager is not None)
    health_checker.add_check("message_queue", lambda: message_queue is not None)

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    checks = health_checker.run_health_checks()
    overall_status = "healthy" if all(
        check["status"] == "healthy" for check in checks.values()
    ) else "unhealthy"
    
    return {
        "service": "storage-service",
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/metrics")
async def get_metrics():
    """Получает метрики сервиса"""
    return {
        "service": "storage-service",
        "metrics": metrics_collector.get_metrics(),
        "timestamp": datetime.now().isoformat()
    }

@timing_decorator(metrics_collector)
@app.post("/sheets/write")
async def write_to_sheets(data: Dict[str, Any]):
    """Записывает данные в Google Sheets"""
    try:
        # Валидируем данные
        if "sheet_name" not in data or "data" not in data:
            raise HTTPException(status_code=400, detail="Missing required fields: sheet_name, data")
        
        sheet_name = data["sheet_name"]
        sheet_data = data["data"]
        
        # Записываем в Google Sheets
        success = sheets_manager.write_data(sheet_name, sheet_data)
        
        if success:
            # Сохраняем в историю
            storage_history.append({
                "id": ServiceUtils.generate_correlation_id(),
                "operation": "write",
                "sheet_name": sheet_name,
                "data_size": len(sheet_data),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            # Отправляем событие об успешной записи
            message_queue.publish_event(
                "sheets_data_written",
                {
                    "sheet_name": sheet_name,
                    "data_size": len(sheet_data),
                    "timestamp": datetime.now().isoformat()
                },
                routing_key="storage_events"
            )
            
            metrics_collector.record_counter("sheets_writes", 1)
            logger.info(f"Данные записаны в таблицу: {sheet_name}")
            
            return {
                "status": "success",
                "sheet_name": sheet_name,
                "rows_written": len(sheet_data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            metrics_collector.record_counter("sheets_write_errors", 1)
            raise HTTPException(status_code=500, detail="Failed to write to Google Sheets")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка записи в Google Sheets: {e}")
        metrics_collector.record_counter("sheets_errors", 1)
        
        # Отправляем событие об ошибке
        message_queue.publish_event(
            "sheets_write_error",
            {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            routing_key="storage_events"
        )
        
        raise HTTPException(status_code=500, detail=f"Sheets write failed: {str(e)}")

@app.get("/sheets/read/{sheet_name}")
async def read_from_sheets(sheet_name: str):
    """Читает данные из Google Sheets"""
    try:
        # Читаем данные из Google Sheets
        data = sheets_manager.read_data(sheet_name)
        
        if data:
            metrics_collector.record_counter("sheets_reads", 1)
            logger.info(f"Данные прочитаны из таблицы: {sheet_name}")
            
            return {
                "sheet_name": sheet_name,
                "data": data,
                "rows_count": len(data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"No data found in sheet: {sheet_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка чтения из Google Sheets: {e}")
        metrics_collector.record_counter("sheets_read_errors", 1)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reports/save")
async def save_report(report: Dict[str, Any]):
    """Сохраняет отчет"""
    try:
        # Валидируем отчет
        if "type" not in report or "data" not in report:
            raise HTTPException(status_code=400, detail="Missing required fields: type, data")
        
        report_type = report["type"]
        report_data = report["data"]
        
        # Определяем имя листа на основе типа отчета
        sheet_name = f"{report_type}_reports"
        
        # Сохраняем отчет
        success = sheets_manager.write_data(sheet_name, report_data)
        
        if success:
            # Сохраняем в историю
            storage_history.append({
                "id": ServiceUtils.generate_correlation_id(),
                "operation": "save_report",
                "report_type": report_type,
                "sheet_name": sheet_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            # Отправляем событие о сохранении отчета
            message_queue.publish_event(
                "report_saved",
                {
                    "report_type": report_type,
                    "sheet_name": sheet_name,
                    "timestamp": datetime.now().isoformat()
                },
                routing_key="storage_events"
            )
            
            metrics_collector.record_counter("reports_saved", 1)
            logger.info(f"Отчет сохранен: {report_type}")
            
            return {
                "status": "success",
                "report_type": report_type,
                "sheet_name": sheet_name,
                "timestamp": datetime.now().isoformat()
            }
        else:
            metrics_collector.record_counter("report_save_errors", 1)
            raise HTTPException(status_code=500, detail="Failed to save report")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сохранения отчета: {e}")
        metrics_collector.record_counter("report_errors", 1)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports")
async def get_reports():
    """Получает список отчетов"""
    try:
        # Получаем список доступных отчетов
        reports = [
            {
                "name": "purchase_forecast",
                "description": "Прогноз закупок",
                "sheet_name": "purchase_forecast_reports",
                "last_updated": datetime.now().isoformat()
            },
            {
                "name": "api_health",
                "description": "Здоровье API",
                "sheet_name": "api_health_reports",
                "last_updated": datetime.now().isoformat()
            },
            {
                "name": "performance_metrics",
                "description": "Метрики производительности",
                "sheet_name": "performance_metrics_reports",
                "last_updated": datetime.now().isoformat()
            }
        ]
        
        return {
            "reports": reports,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения списка отчетов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/{report_name}")
async def get_report(report_name: str):
    """Получает конкретный отчет"""
    try:
        # Определяем имя листа
        sheet_name = f"{report_name}_reports"
        
        # Читаем данные отчета
        data = sheets_manager.read_data(sheet_name)
        
        if data:
            return {
                "report_name": report_name,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Report not found: {report_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backup/create")
async def create_backup():
    """Создает резервную копию данных"""
    try:
        # Заглушка для создания резервной копии
        backup_id = ServiceUtils.generate_correlation_id()
        
        # Сохраняем в историю
        storage_history.append({
            "id": backup_id,
            "operation": "backup_create",
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })
        
        # Отправляем событие о создании резервной копии
        message_queue.publish_event(
            "backup_created",
            {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat()
            },
            routing_key="storage_events"
        )
        
        metrics_collector.record_counter("backups_created", 1)
        logger.info(f"Резервная копия создана: {backup_id}")
        
        return {
            "backup_id": backup_id,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания резервной копии: {e}")
        metrics_collector.record_counter("backup_errors", 1)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/backup/list")
async def list_backups():
    """Получает список резервных копий"""
    # Заглушка для списка резервных копий
    return {
        "backups": [
            {
                "id": "backup_001",
                "created_at": datetime.now().isoformat(),
                "size": "1.2MB",
                "status": "completed"
            }
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/files")
async def list_files():
    """Получает список файлов"""
    # Заглушка для списка файлов
    return {
        "files": [
            {
                "name": "forecast_report.csv",
                "size": "256KB",
                "created_at": datetime.now().isoformat(),
                "type": "csv"
            }
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/history")
async def get_storage_history(limit: int = 50):
    """Получает историю операций с хранилищем"""
    return {
        "history": storage_history[-limit:] if storage_history else [],
        "total_count": len(storage_history),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005) 