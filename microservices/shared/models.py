"""
Общие модели данных для микросервисов
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
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
# Notification Models
# ============================================================================

class NotificationRequest(BaseModel):
    """Запрос на отправку уведомления"""
    type: NotificationType = Field(..., description="Тип уведомления")
    title: str = Field(..., description="Заголовок")
    message: str = Field(..., description="Сообщение")
    recipients: List[str] = Field(..., description="Получатели")
    data: Optional[Dict[str, Any]] = Field(None, description="Дополнительные данные")

class NotificationResponse(BaseResponse):
    """Ответ на отправку уведомления"""
    notification_id: str = Field(..., description="ID уведомления")
    sent_at: datetime = Field(..., description="Время отправки")
    recipients_count: int = Field(..., description="Количество получателей")

class NotificationHistory(BaseResponse):
    """История уведомлений"""
    notifications: List[Dict[str, Any]] = Field(..., description="Список уведомлений")
    total: int = Field(..., description="Общее количество")

# ============================================================================
# Monitoring Models
# ============================================================================

class HealthCheck(BaseModel):
    """Проверка здоровья сервиса"""
    service: str = Field(..., description="Название сервиса")
    status: str = Field(..., description="Статус")
    timestamp: datetime = Field(..., description="Временная метка")
    response_time: Optional[float] = Field(None, description="Время отклика")
    details: Optional[Dict[str, Any]] = Field(None, description="Детали")

class MetricsData(BaseModel):
    """Метрики сервиса"""
    service: str = Field(..., description="Название сервиса")
    metrics: Dict[str, Any] = Field(..., description="Метрики")
    timestamp: datetime = Field(..., description="Временная метка")

class Alert(BaseModel):
    """Алерт"""
    id: str = Field(..., description="ID алерта")
    service: str = Field(..., description="Сервис")
    severity: str = Field(..., description="Важность")
    message: str = Field(..., description="Сообщение")
    timestamp: datetime = Field(..., description="Временная метка")
    resolved: bool = Field(default=False, description="Разрешен")

# ============================================================================
# Storage Models
# ============================================================================

class FileUpload(BaseModel):
    """Загрузка файла"""
    filename: str = Field(..., description="Имя файла")
    content_type: str = Field(..., description="Тип содержимого")
    size: int = Field(..., description="Размер файла")
    data: bytes = Field(..., description="Данные файла")

class FileInfo(BaseModel):
    """Информация о файле"""
    id: str = Field(..., description="ID файла")
    filename: str = Field(..., description="Имя файла")
    content_type: str = Field(..., description="Тип содержимого")
    size: int = Field(..., description="Размер файла")
    created_at: datetime = Field(..., description="Дата создания")
    url: Optional[str] = Field(None, description="URL для скачивания")

class SheetsUpdate(BaseModel):
    """Обновление Google Sheets"""
    spreadsheet_id: str = Field(..., description="ID таблицы")
    sheet_name: str = Field(..., description="Название листа")
    data: List[List[Any]] = Field(..., description="Данные для записи")
    range: Optional[str] = Field(None, description="Диапазон")

# ============================================================================
# API Models
# ============================================================================

class APIMetrics(BaseModel):
    """Метрики API"""
    endpoint: str = Field(..., description="Эндпоинт")
    method: str = Field(..., description="HTTP метод")
    response_time: float = Field(..., description="Время отклика (мс)")
    status_code: int = Field(..., description="HTTP статус код")
    timestamp: datetime = Field(..., description="Временная метка")
    user_agent: Optional[str] = Field(None, description="User Agent")
    ip_address: Optional[str] = Field(None, description="IP адрес")

class APIHealth(BaseModel):
    """Здоровье API"""
    service: str = Field(..., description="Название сервиса")
    status: str = Field(..., description="Статус")
    version: str = Field(..., description="Версия")
    uptime: float = Field(..., description="Время работы (сек)")
    memory_usage: Optional[float] = Field(None, description="Использование памяти (%)")
    cpu_usage: Optional[float] = Field(None, description="Использование CPU (%)")
    active_connections: Optional[int] = Field(None, description="Активные соединения") 