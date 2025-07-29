"""
Storage Service - управление Google Sheets и файлами
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import csv
import pandas as pd
from pathlib import Path

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    ExportRequest, ExportResponse, BackupRequest, BackupResponse,
    FileInfo, StorageStats, BaseResponse, ErrorResponse
)
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient,
    DatabaseClient, handle_service_error, ServiceException
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('storage-service', config['log_level'])

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
    logger.info("Storage Service запускается...")
    yield
    # Shutdown
    logger.info("Storage Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="Storage Service",
    description="Сервис для управления Google Sheets, экспорта данных и резервного копирования",
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
# Класс для работы с Google Sheets
# ============================================================================

class GoogleSheetsManager:
    """Класс для работы с Google Sheets"""

    def __init__(self, credentials_path: str = None):
        self.credentials_path = credentials_path or "credentials.json"
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Инициализация Google Sheets API"""
        try:
            # В реальной системе здесь будет инициализация Google Sheets API
            # Пока используем заглушку
            logger.info("Google Sheets API инициализирован")
            self.service = True
        except Exception as e:
            logger.error(f"Ошибка инициализации Google Sheets API: {e}")
            self.service = None

    def create_spreadsheet(self, title: str, data: List[List[Any]] = None) -> Dict[str, Any]:
        """Создает новую таблицу"""
        try:
            if not self.service:
                raise Exception("Google Sheets API не инициализирован")

            # Заглушка для создания таблицы
            spreadsheet_id = f"spreadsheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            result = {
                'spreadsheet_id': spreadsheet_id,
                'title': title,
                'url': f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                'created_at': datetime.now().isoformat()
            }

            if data:
                # Здесь будет логика добавления данных
                result['rows_added'] = len(data)

            logger.info(f"Создана таблица: {title} (ID: {spreadsheet_id})")
            return result

        except Exception as e:
            logger.error(f"Ошибка создания таблицы: {e}")
            raise

    def update_spreadsheet(self, spreadsheet_id: str, data: List[List[Any]], 
                          sheet_name: str = "Sheet1") -> bool:
        """Обновляет данные в таблице"""
        try:
            if not self.service:
                raise Exception("Google Sheets API не инициализирован")

            # Заглушка для обновления таблицы
            logger.info(f"Обновлена таблица {spreadsheet_id}: {len(data)} строк")
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления таблицы: {e}")
            return False

    def read_spreadsheet(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> List[List[Any]]:
        """Читает данные из таблицы"""
        try:
            if not self.service:
                raise Exception("Google Sheets API не инициализирован")

            # Заглушка для чтения таблицы
            logger.info(f"Чтение таблицы {spreadsheet_id}")
            return []

        except Exception as e:
            logger.error(f"Ошибка чтения таблицы: {e}")
            return []

    def share_spreadsheet(self, spreadsheet_id: str, email: str, role: str = "reader") -> bool:
        """Предоставляет доступ к таблице"""
        try:
            if not self.service:
                raise Exception("Google Sheets API не инициализирован")

            # Заглушка для предоставления доступа
            logger.info(f"Предоставлен доступ к таблице {spreadsheet_id} для {email}")
            return True

        except Exception as e:
            logger.error(f"Ошибка предоставления доступа: {e}")
            return False

# ============================================================================
# Класс для экспорта данных
# ============================================================================

class DataExporter:
    """Класс для экспорта данных в различные форматы"""

    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def export_to_csv(self, data: List[Dict[str, Any]], filename: str = None) -> str:
        """Экспортирует данные в CSV"""
        try:
            if not data:
                raise ValueError("Нет данных для экспорта")

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"export_{timestamp}.csv"

            filepath = self.storage_dir / filename

            # Создаем DataFrame
            df = pd.DataFrame(data)

            # Экспортируем в CSV
            df.to_csv(filepath, index=False, encoding='utf-8')

            logger.info(f"Данные экспортированы в CSV: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка экспорта в CSV: {e}")
            raise

    def export_to_json(self, data: List[Dict[str, Any]], filename: str = None) -> str:
        """Экспортирует данные в JSON"""
        try:
            if not data:
                raise ValueError("Нет данных для экспорта")

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"export_{timestamp}.json"

            filepath = self.storage_dir / filename

            # Добавляем метаинформацию
            export_data = {
                'metadata': {
                    'exported_at': datetime.now().isoformat(),
                    'total_records': len(data),
                    'format': 'json'
                },
                'data': data
            }

            # Экспортируем в JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Данные экспортированы в JSON: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка экспорта в JSON: {e}")
            raise

    def export_to_excel(self, data: List[Dict[str, Any]], filename: str = None) -> str:
        """Экспортирует данные в Excel"""
        try:
            if not data:
                raise ValueError("Нет данных для экспорта")

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"export_{timestamp}.xlsx"

            filepath = self.storage_dir / filename

            # Создаем DataFrame
            df = pd.DataFrame(data)

            # Экспортируем в Excel
            df.to_excel(filepath, index=False, engine='openpyxl')

            logger.info(f"Данные экспортированы в Excel: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка экспорта в Excel: {e}")
            raise

    def export_forecast_data(self, forecast_data: List[Dict[str, Any]], 
                           format: str = "csv") -> str:
        """Экспортирует данные прогноза"""
        try:
            if format == "csv":
                return self.export_to_csv(forecast_data, f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            elif format == "json":
                return self.export_to_json(forecast_data, f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            elif format == "excel":
                return self.export_to_excel(forecast_data, f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            else:
                raise ValueError(f"Неподдерживаемый формат: {format}")

        except Exception as e:
            logger.error(f"Ошибка экспорта данных прогноза: {e}")
            raise

# ============================================================================
# Класс для резервного копирования
# ============================================================================

class BackupManager:
    """Класс для управления резервными копиями"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, data: Dict[str, Any], backup_type: str = "manual") -> str:
        """Создает резервную копию"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backup_{backup_type}_{timestamp}.json"
            filepath = self.backup_dir / filename

            # Добавляем метаинформацию
            backup_data = {
                'metadata': {
                    'backup_type': backup_type,
                    'created_at': datetime.now().isoformat(),
                    'version': '1.0'
                },
                'data': data
            }

            # Сохраняем резервную копию
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Создана резервная копия: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка создания резервной копии: {e}")
            raise

    def restore_backup(self, backup_file: str) -> Dict[str, Any]:
        """Восстанавливает данные из резервной копии"""
        try:
            filepath = Path(backup_file)
            if not filepath.exists():
                raise FileNotFoundError(f"Файл резервной копии не найден: {backup_file}")

            with open(filepath, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            logger.info(f"Восстановлена резервная копия: {backup_file}")
            return backup_data

        except Exception as e:
            logger.error(f"Ошибка восстановления резервной копии: {e}")
            raise

    def list_backups(self) -> List[Dict[str, Any]]:
        """Получает список резервных копий"""
        try:
            backups = []
            for filepath in self.backup_dir.glob("backup_*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    
                    backups.append({
                        'filename': filepath.name,
                        'filepath': str(filepath),
                        'size': filepath.stat().st_size,
                        'created_at': backup_data.get('metadata', {}).get('created_at'),
                        'backup_type': backup_data.get('metadata', {}).get('backup_type')
                    })
                except Exception as e:
                    logger.warning(f"Ошибка чтения резервной копии {filepath}: {e}")

            # Сортируем по дате создания
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return backups

        except Exception as e:
            logger.error(f"Ошибка получения списка резервных копий: {e}")
            return []

    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Удаляет старые резервные копии"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            deleted_count = 0

            for filepath in self.backup_dir.glob("backup_*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    
                    created_at = datetime.fromisoformat(
                        backup_data.get('metadata', {}).get('created_at', '1970-01-01T00:00:00')
                    )

                    if created_at < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                        logger.info(f"Удалена старая резервная копия: {filepath.name}")

                except Exception as e:
                    logger.warning(f"Ошибка обработки резервной копии {filepath}: {e}")

            logger.info(f"Удалено {deleted_count} старых резервных копий")
            return deleted_count

        except Exception as e:
            logger.error(f"Ошибка очистки старых резервных копий: {e}")
            return 0

# ============================================================================
# Класс для управления файлами
# ============================================================================

class FileManager:
    """Класс для управления файлами"""

    def __init__(self, files_dir: str = "files"):
        self.files_dir = Path(files_dir)
        self.files_dir.mkdir(exist_ok=True)

    def save_file(self, file: UploadFile, subdirectory: str = None) -> str:
        """Сохраняет загруженный файл"""
        try:
            # Создаем поддиректорию если указана
            if subdirectory:
                save_dir = self.files_dir / subdirectory
                save_dir.mkdir(exist_ok=True)
            else:
                save_dir = self.files_dir

            # Генерируем уникальное имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file.filename}"
            filepath = save_dir / filename

            # Сохраняем файл
            with open(filepath, "wb") as f:
                content = file.file.read()
                f.write(content)

            logger.info(f"Файл сохранен: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            raise

    def get_file_info(self, filepath: str) -> Dict[str, Any]:
        """Получает информацию о файле"""
        try:
            path = Path(filepath)
            if not path.exists():
                raise FileNotFoundError(f"Файл не найден: {filepath}")

            stat = path.stat()
            return {
                'filename': path.name,
                'filepath': str(path),
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'extension': path.suffix
            }

        except Exception as e:
            logger.error(f"Ошибка получения информации о файле: {e}")
            raise

    def list_files(self, subdirectory: str = None) -> List[Dict[str, Any]]:
        """Получает список файлов"""
        try:
            if subdirectory:
                list_dir = self.files_dir / subdirectory
            else:
                list_dir = self.files_dir

            if not list_dir.exists():
                return []

            files = []
            for filepath in list_dir.iterdir():
                if filepath.is_file():
                    files.append(self.get_file_info(str(filepath)))

            # Сортируем по дате создания
            files.sort(key=lambda x: x['created_at'], reverse=True)
            return files

        except Exception as e:
            logger.error(f"Ошибка получения списка файлов: {e}")
            return []

    def delete_file(self, filepath: str) -> bool:
        """Удаляет файл"""
        try:
            path = Path(filepath)
            if not path.exists():
                return False

            path.unlink()
            logger.info(f"Файл удален: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления файла: {e}")
            return False

# ============================================================================
# Инициализация компонентов
# ============================================================================

sheets_manager = GoogleSheetsManager()
data_exporter = DataExporter()
backup_manager = BackupManager()
file_manager = FileManager()

# ============================================================================
# Эндпоинты
# ============================================================================

@app.get("/health")
@handle_service_error
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "service": "storage-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": config['version']
    }

@app.post("/sheets/create")
@handle_service_error
async def create_spreadsheet(
    title: str,
    data: List[List[Any]] = None,
    background_tasks: BackgroundTasks = None,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Создание новой Google таблицы"""
    logger.info(f"Запрос на создание таблицы: {title}")

    result = sheets_manager.create_spreadsheet(title, data)

    # Отправляем событие в очередь
    event = {
        'event_type': 'spreadsheet_created',
        'service': 'storage-service',
        'data': {
            'spreadsheet_id': result['spreadsheet_id'],
            'title': title,
            'timestamp': datetime.now().isoformat()
        }
    }

    rabbitmq_client.publish_message('storage.events', event)

    return {
        'success': True,
        'spreadsheet': result
    }

@app.post("/sheets/update/{spreadsheet_id}")
@handle_service_error
async def update_spreadsheet(
    spreadsheet_id: str,
    data: List[List[Any]],
    sheet_name: str = "Sheet1"
):
    """Обновление данных в Google таблице"""
    logger.info(f"Запрос на обновление таблицы: {spreadsheet_id}")

    success = sheets_manager.update_spreadsheet(spreadsheet_id, data, sheet_name)

    return {
        'success': success,
        'message': "Таблица обновлена" if success else "Ошибка обновления таблицы"
    }

@app.get("/sheets/read/{spreadsheet_id}")
@handle_service_error
async def read_spreadsheet(
    spreadsheet_id: str,
    sheet_name: str = "Sheet1"
):
    """Чтение данных из Google таблицы"""
    logger.info(f"Запрос на чтение таблицы: {spreadsheet_id}")

    data = sheets_manager.read_spreadsheet(spreadsheet_id, sheet_name)

    return {
        'success': True,
        'data': data,
        'total_rows': len(data)
    }

@app.post("/sheets/share/{spreadsheet_id}")
@handle_service_error
async def share_spreadsheet(
    spreadsheet_id: str,
    email: str,
    role: str = "reader"
):
    """Предоставление доступа к Google таблице"""
    logger.info(f"Запрос на предоставление доступа к таблице {spreadsheet_id} для {email}")

    success = sheets_manager.share_spreadsheet(spreadsheet_id, email, role)

    return {
        'success': success,
        'message': "Доступ предоставлен" if success else "Ошибка предоставления доступа"
    }

@app.post("/export/data")
@handle_service_error
async def export_data(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Экспорт данных в различные форматы"""
    logger.info(f"Запрос на экспорт данных в формате {request.format}")

    try:
        if request.format == "csv":
            filepath = data_exporter.export_to_csv(request.data)
        elif request.format == "json":
            filepath = data_exporter.export_to_json(request.data)
        elif request.format == "excel":
            filepath = data_exporter.export_to_excel(request.data)
        else:
            raise ValueError(f"Неподдерживаемый формат: {request.format}")

        # Отправляем событие в очередь
        event = {
            'event_type': 'data_exported',
            'service': 'storage-service',
            'data': {
                'format': request.format,
                'filepath': filepath,
                'records_count': len(request.data),
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('storage.events', event)

        return ExportResponse(
            success=True,
            filepath=filepath,
            format=request.format,
            records_count=len(request.data)
        )

    except Exception as e:
        logger.error(f"Ошибка экспорта данных: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/forecast")
@handle_service_error
async def export_forecast(
    forecast_data: List[Dict[str, Any]],
    format: str = "csv",
    background_tasks: BackgroundTasks = None,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Экспорт данных прогноза"""
    logger.info(f"Запрос на экспорт прогноза в формате {format}")

    try:
        filepath = data_exporter.export_forecast_data(forecast_data, format)

        # Отправляем событие в очередь
        event = {
            'event_type': 'forecast_exported',
            'service': 'storage-service',
            'data': {
                'format': format,
                'filepath': filepath,
                'records_count': len(forecast_data),
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('storage.events', event)

        return {
            'success': True,
            'filepath': filepath,
            'format': format,
            'records_count': len(forecast_data)
        }

    except Exception as e:
        logger.error(f"Ошибка экспорта прогноза: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backup/create")
@handle_service_error
async def create_backup(
    request: BackupRequest,
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Создание резервной копии"""
    logger.info(f"Запрос на создание резервной копии типа: {request.backup_type}")

    try:
        filepath = backup_manager.create_backup(request.data, request.backup_type)

        # Отправляем событие в очередь
        event = {
            'event_type': 'backup_created',
            'service': 'storage-service',
            'data': {
                'backup_type': request.backup_type,
                'filepath': filepath,
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('storage.events', event)

        return BackupResponse(
            success=True,
            filepath=filepath,
            backup_type=request.backup_type
        )

    except Exception as e:
        logger.error(f"Ошибка создания резервной копии: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backup/restore")
@handle_service_error
async def restore_backup(backup_file: str):
    """Восстановление из резервной копии"""
    logger.info(f"Запрос на восстановление из резервной копии: {backup_file}")

    try:
        backup_data = backup_manager.restore_backup(backup_file)

        return {
            'success': True,
            'backup_data': backup_data,
            'restored_at': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка восстановления резервной копии: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/backup/list")
@handle_service_error
async def list_backups():
    """Получение списка резервных копий"""
    logger.info("Запрос списка резервных копий")

    backups = backup_manager.list_backups()

    return {
        'success': True,
        'backups': backups,
        'count': len(backups)
    }

@app.post("/backup/cleanup")
@handle_service_error
async def cleanup_backups(keep_days: int = 30):
    """Очистка старых резервных копий"""
    logger.info(f"Запрос на очистку резервных копий старше {keep_days} дней")

    deleted_count = backup_manager.cleanup_old_backups(keep_days)

    return {
        'success': True,
        'deleted_count': deleted_count,
        'keep_days': keep_days
    }

@app.post("/files/upload")
@handle_service_error
async def upload_file(
    file: UploadFile = File(...),
    subdirectory: str = None
):
    """Загрузка файла"""
    logger.info(f"Запрос на загрузку файла: {file.filename}")

    try:
        filepath = file_manager.save_file(file, subdirectory)

        return {
            'success': True,
            'filepath': filepath,
            'filename': file.filename,
            'size': file.size
        }

    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/list")
@handle_service_error
async def list_files(subdirectory: str = None):
    """Получение списка файлов"""
    logger.info(f"Запрос списка файлов в директории: {subdirectory or 'root'}")

    files = file_manager.list_files(subdirectory)

    return {
        'success': True,
        'files': files,
        'count': len(files)
    }

@app.get("/files/info/{filepath:path}")
@handle_service_error
async def get_file_info(filepath: str):
    """Получение информации о файле"""
    logger.info(f"Запрос информации о файле: {filepath}")

    try:
        file_info = file_manager.get_file_info(filepath)
        return {
            'success': True,
            'file_info': file_info
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")
    except Exception as e:
        logger.error(f"Ошибка получения информации о файле: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/delete/{filepath:path}")
@handle_service_error
async def delete_file(filepath: str):
    """Удаление файла"""
    logger.info(f"Запрос на удаление файла: {filepath}")

    success = file_manager.delete_file(filepath)

    return {
        'success': success,
        'message': "Файл удален" if success else "Файл не найден"
    }

@app.get("/storage/stats")
@handle_service_error
async def get_storage_stats():
    """Получение статистики хранилища"""
    logger.info("Запрос статистики хранилища")

    try:
        # Статистика файлов
        files = file_manager.list_files()
        total_files = len(files)
        total_size = sum(f['size'] for f in files)

        # Статистика резервных копий
        backups = backup_manager.list_backups()
        total_backups = len(backups)
        backup_size = sum(b['size'] for b in backups)

        stats = {
            'files': {
                'count': total_files,
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            },
            'backups': {
                'count': total_backups,
                'total_size': backup_size,
                'total_size_mb': round(backup_size / (1024 * 1024), 2)
            },
            'storage': {
                'total_size': total_size + backup_size,
                'total_size_mb': round((total_size + backup_size) / (1024 * 1024), 2)
            }
        }

        return {
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики хранилища: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Фоновые задачи
# ============================================================================

async def periodic_backup():
    """Периодическое создание резервных копий"""
    try:
        # Здесь будет логика автоматического резервного копирования
        logger.info("Периодическое резервное копирование завершено")
    except Exception as e:
        logger.error(f"Ошибка периодического резервного копирования: {e}")

async def cleanup_old_files():
    """Очистка старых файлов"""
    try:
        # Здесь будет логика очистки старых файлов
        logger.info("Очистка старых файлов завершена")
    except Exception as e:
        logger.error(f"Ошибка очистки старых файлов: {e}")

# ============================================================================
# Обработчик событий из очереди
# ============================================================================

def handle_storage_event(ch, method, properties, body):
    """Обработчик событий из очереди"""
    try:
        event = json.loads(body)
        event_type = event.get('event_type')
        
        logger.info(f"Получено событие хранилища: {event_type}")
        
        if event_type == 'export_forecast':
            # Обработка экспорта прогноза
            data = event.get('data', {})
            logger.info(f"Экспорт прогноза: {data.get('format')} - {data.get('records_count')} записей")
            
        elif event_type == 'backup_request':
            # Обработка запроса резервного копирования
            data = event.get('data', {})
            logger.info(f"Запрос резервного копирования: {data.get('backup_type')}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки события хранилища: {e}")

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level=config['log_level'].lower()
    ) 