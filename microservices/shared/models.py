"""
Общие модели данных для микросервисов
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

# ============================================================================
# Enums
# ============================================================================

class ForecastQuality(str, Enum):
    """Качество прогноза"""
    GOOD = "GOOD"
    LOW_DATA = "LOW_DATA"
    NO_SALES = "NO_SALES"
    NO_SALES_DATA = "NO_SALES_DATA"

class ConfidenceLevel(str, Enum):
    """Уровень уверенности"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"

class UrgencyLevel(str, Enum):
    """Уровень срочности"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class NotificationType(str, Enum):
    """Тип уведомления"""
    FORECAST = "forecast"
    ALERT = "alert"
    ERROR = "error"
    INFO = "info"

# ============================================================================
# Base Models
# ============================================================================

class BaseResponse(BaseModel):
    """Базовая модель ответа"""
    success: bool = Field(..., description="Успешность операции")
    message: Optional[str] = Field(None, description="Сообщение")
    timestamp: datetime = Field(default_factory=datetime.now, description="Временная метка")

class ErrorResponse(BaseResponse):
    """Модель ошибки"""
    error_code: str = Field(..., description="Код ошибки")
    details: Optional[Dict[str, Any]] = Field(None, description="Детали ошибки")

# ============================================================================
# Product Models
# ============================================================================

class Product(BaseModel):
    """Модель товара"""
    sku: str = Field(..., description="SKU товара")
    name: Optional[str] = Field(None, description="Название товара")
    category: Optional[str] = Field(None, description="Категория")
    moq: int = Field(default=1, description="Минимальная партия")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ProductList(BaseResponse):
    """Список товаров"""
    products: List[Product] = Field(..., description="Список товаров")
    total: int = Field(..., description="Общее количество")

# ============================================================================
# Sales Models
# ============================================================================

class SalesRecord(BaseModel):
    """Запись о продажах"""
    sku: str = Field(..., description="SKU товара")
    date: datetime = Field(..., description="Дата продажи")
    quantity: int = Field(..., description="Количество проданных единиц")
    revenue: Optional[float] = Field(None, description="Выручка")
    created_at: datetime = Field(default_factory=datetime.now)

class SalesData(BaseResponse):
    """Данные о продажах"""
    sales: List[SalesRecord] = Field(..., description="Записи о продажах")
    total_records: int = Field(..., description="Общее количество записей")
    date_range: Dict[str, datetime] = Field(..., description="Диапазон дат")

# ============================================================================
# Stock Models
# ============================================================================

class StockRecord(BaseModel):
    """Запись об остатках"""
    sku: str = Field(..., description="SKU товара")
    stock: int = Field(..., description="Общий остаток")
    reserved: int = Field(..., description="Зарезервированный остаток")
    available: int = Field(..., description="Доступный остаток")
    updated_at: datetime = Field(default_factory=datetime.now)

class StockData(BaseResponse):
    """Данные об остатках"""
    stocks: List[StockRecord] = Field(..., description="Записи об остатках")
    total_skus: int = Field(..., description="Общее количество SKU")

# ============================================================================
# Forecast Models
# ============================================================================

class ForecastItem(BaseModel):
    """Элемент прогноза"""
    sku: str = Field(..., description="SKU товара")
    avg_daily_sales: float = Field(..., description="Средняя дневная продажа")
    current_stock: int = Field(..., description="Текущий остаток")
    days_until_stockout: float = Field(..., description="Дней до исчерпания")
    recommended_quantity: int = Field(..., description="Рекомендуемое количество")
    moq: int = Field(..., description="Минимальная партия")
    forecast_quality: ForecastQuality = Field(..., description="Качество прогноза")
    confidence: ConfidenceLevel = Field(..., description="Уровень уверенности")
    urgency: UrgencyLevel = Field(..., description="Срочность")

class ForecastRequest(BaseModel):
    """Запрос на расчет прогноза"""
    sales_data: List[SalesRecord] = Field(..., description="Данные о продажах")
    stocks_data: List[StockRecord] = Field(..., description="Данные об остатках")
    days_forecast_short: int = Field(default=40, description="Краткосрочный прогноз")
    days_forecast_long: int = Field(default=120, description="Долгосрочный прогноз")

class ForecastResponse(BaseResponse):
    """Ответ с прогнозом"""
    forecast: List[ForecastItem] = Field(..., description="Прогноз закупок")
    analytics: Dict[str, Any] = Field(..., description="Аналитика")
    recommendations: List[Dict[str, Any]] = Field(..., description="Рекомендации")
    total_items: int = Field(..., description="Общее количество позиций")

class SeasonalityData(BaseModel):
    """Данные о сезонности"""
    daily_pattern: List[Dict[str, Any]] = Field(..., description="Паттерн по дням недели")
    monthly_pattern: List[Dict[str, Any]] = Field(..., description="Паттерн по месяцам")
    peak_day: Dict[str, Any] = Field(..., description="Пиковый день")
    peak_month: Dict[str, Any] = Field(..., description="Пиковый месяц")

# ============================================================================
# Модели для Notification Service
# ============================================================================

class NotificationRequest(BaseModel):
    """Запрос на отправку уведомления"""
    notification_type: str
    message: str = None
    template_name: str = None
    template_data: Dict[str, Any] = {}

class NotificationResponse(BaseModel):
    """Ответ на отправку уведомления"""
    success: bool
    message: str
    notification_id: str = None

class NotificationHistory(BaseModel):
    """История уведомлений"""
    success: bool
    notifications: List[Dict[str, Any]]
    total_count: int

class SubscriptionRequest(BaseModel):
    """Запрос на подписку"""
    user_id: str
    notification_types: List[str]

class SubscriptionResponse(BaseModel):
    """Ответ на подписку"""
    success: bool
    message: str

class TemplateRequest(BaseModel):
    """Запрос на создание шаблона"""
    name: str
    title: str
    template: str

# ============================================================================
# Модели для Monitoring Service
# ============================================================================

class HealthCheck(BaseModel):
    """Проверка здоровья сервиса"""
    service: str
    status: str
    response_time: float = None
    details: Dict[str, Any] = {}
    timestamp: str

class MetricsData(BaseModel):
    """Данные метрик"""
    system: Dict[str, Any] = {}
    api: Dict[str, Any] = {}
    timestamp: str

class AlertData(BaseModel):
    """Данные алерта"""
    type: str
    severity: str
    message: str
    details: Dict[str, Any] = {}
    timestamp: str

class DashboardData(BaseModel):
    """Данные для дашборда"""
    overview: Dict[str, Any] = {}
    alerts: Dict[str, Any] = {}
    system: Dict[str, Any] = {}
    services: List[Dict[str, Any]] = []
    recent_alerts: List[Dict[str, Any]] = []
    timestamp: str

# ============================================================================
# Модели для Storage Service
# ============================================================================

class ExportRequest(BaseModel):
    """Запрос на экспорт данных"""
    data: List[Dict[str, Any]]
    format: str = "csv"  # csv, json, excel

class ExportResponse(BaseModel):
    """Ответ на экспорт данных"""
    success: bool
    filepath: str = None
    format: str = None
    records_count: int = 0

class BackupRequest(BaseModel):
    """Запрос на создание резервной копии"""
    data: Dict[str, Any]
    backup_type: str = "manual"

class BackupResponse(BaseModel):
    """Ответ на создание резервной копии"""
    success: bool
    filepath: str = None
    backup_type: str = None

class FileInfo(BaseModel):
    """Информация о файле"""
    filename: str
    filepath: str
    size: int
    created_at: str
    modified_at: str
    extension: str

class StorageStats(BaseModel):
    """Статистика хранилища"""
    files: Dict[str, Any] = {}
    backups: Dict[str, Any] = {}
    storage: Dict[str, Any] = {}

# ============================================================================
# ML Service Models
# ============================================================================

class ModelTrainingRequest(BaseModel):
    """Запрос на обучение ML моделей"""
    sales_data: List[Dict[str, Any]]

class ModelTrainingResponse(BaseModel):
    """Ответ обучения ML моделей"""
    success: bool
    message: str = None
    results: Dict[str, Any] = {}
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def _set_ts(cls, v):
        return v or datetime.now().isoformat()

class MLPredictionRequest(BaseModel):
    """Запрос предсказаний ML"""
    features: List[Dict[str, Any]]
    sku: Optional[str] = None
    steps: int = 30

class MLPredictionResponse(BaseModel):
    """Ответ предсказаний ML"""
    success: bool
    predictions: Dict[str, Any]
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def _set_ts_pred(cls, v):
        return v or datetime.now().isoformat()

class ModelEvaluationResponse(BaseModel):
    """Ответ оценки качества ML моделей"""
    success: bool
    evaluation: Dict[str, Any]
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def _set_ts_eval(cls, v):
        return v or datetime.now().isoformat()

# ============================================================================
# Enums для статусов и уровней
# ============================================================================

class ServiceStatus(str, Enum):
    """Статусы сервисов"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    ERROR = "error"

class AlertSeverity(str, Enum):
    """Уровни серьезности алертов"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class NotificationType(str, Enum):
    """Типы уведомлений"""
    FORECAST_ALERT = "forecast_alert"
    STOCK_ALERT = "stock_alert"
    SYSTEM_ALERT = "system_alert"
    ERROR_ALERT = "error_alert"
    SYNC_COMPLETED = "sync_completed"

class ExportFormat(str, Enum):
    """Форматы экспорта"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"

class BackupType(str, Enum):
    """Типы резервных копий"""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SCHEDULED = "scheduled"

# ============================================================================
# Модели для общих ответов
# ============================================================================

class BaseResponse(BaseModel):
    """Базовый ответ API"""
    success: bool
    message: str = None
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.now().isoformat()

class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    success: bool = False
    error_code: str = None
    message: str
    details: Dict[str, Any] = {}
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.now().isoformat()

# ============================================================================
# Модели для событий
# ============================================================================

class EventData(BaseModel):
    """Данные события"""
    event_type: str
    service: str
    data: Dict[str, Any]
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.now().isoformat()

class QueueMessage(BaseModel):
    """Сообщение в очереди"""
    queue: str
    message: Dict[str, Any]
    priority: int = 0
    timestamp: str = None

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.now().isoformat() 