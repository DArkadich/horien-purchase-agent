"""
Forecast Service - расчет прогнозов закупок
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    ForecastRequest, ForecastResponse, ForecastItem, SeasonalityData,
    SalesRecord, StockRecord, BaseResponse, ErrorResponse
)
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient, 
    DatabaseClient, handle_service_error, ServiceException
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('forecast-service', config['log_level'])

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
    logger.info("Forecast Service запускается...")
    yield
    # Shutdown
    logger.info("Forecast Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="Forecast Service",
    description="Сервис для расчета прогнозов закупок",
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
# Класс для расчета прогнозов
# ============================================================================

class ForecastCalculator:
    """Калькулятор прогнозов закупок"""
    
    def __init__(self):
        self.days_forecast_short = 40
        self.days_forecast_long = 120
    
    def calculate_daily_sales(self, sales_data: List[SalesRecord]) -> Dict[str, float]:
        """Рассчитывает среднюю дневную продажу для каждого SKU"""
        daily_sales = {}
        
        # Группируем продажи по SKU
        sales_by_sku = {}
        for sale in sales_data:
            sku = sale.sku
            if sku not in sales_by_sku:
                sales_by_sku[sku] = []
            sales_by_sku[sku].append(sale)
        
        # Рассчитываем среднюю продажу для каждого SKU
        for sku, sales in sales_by_sku.items():
            total_quantity = sum(sale.quantity for sale in sales)
            total_days = len(set(sale.date.date() for sale in sales))
            
            if total_days > 0:
                daily_sales[sku] = total_quantity / total_days
            else:
                daily_sales[sku] = 0.0
        
        return daily_sales
    
    def calculate_forecast(self, sales_data: List[SalesRecord], 
                          stocks_data: List[StockRecord],
                          days_forecast_short: int = 40,
                          days_forecast_long: int = 120) -> List[ForecastItem]:
        """Рассчитывает прогноз закупок"""
        logger.info("Начинаем расчет прогноза закупок")
        
        # Рассчитываем среднюю дневную продажу
        daily_sales = self.calculate_daily_sales(sales_data)
        
        # Создаем словарь остатков
        stocks_dict = {stock.sku: stock for stock in stocks_data}
        
        forecast_items = []
        
        for sku, avg_daily_sales in daily_sales.items():
            # Получаем текущий остаток
            stock = stocks_dict.get(sku)
            if not stock:
                continue
            
            current_stock = stock.available
            
            # Рассчитываем дни до исчерпания
            if avg_daily_sales > 0:
                days_until_stockout = current_stock / avg_daily_sales
            else:
                days_until_stockout = float('inf')
            
            # Определяем необходимость закупки
            needs_purchase = days_until_stockout < days_forecast_short
            
            # Рассчитываем рекомендуемое количество
            if needs_purchase:
                recommended_quantity = max(
                    (days_forecast_long - days_until_stockout) * avg_daily_sales,
                    avg_daily_sales * days_forecast_short
                )
            else:
                recommended_quantity = 0
            
            # Определяем качество прогноза
            sales_count = len([s for s in sales_data if s.sku == sku])
            if sales_count >= 30:
                forecast_quality = "GOOD"
                confidence = "HIGH"
            elif sales_count >= 14:
                forecast_quality = "GOOD"
                confidence = "MEDIUM"
            elif sales_count >= 7:
                forecast_quality = "LOW_DATA"
                confidence = "LOW"
            else:
                forecast_quality = "NO_SALES"
                confidence = "VERY_LOW"
            
            # Определяем срочность
            if days_until_stockout < 10:
                urgency = "HIGH"
            elif days_until_stockout < 20:
                urgency = "MEDIUM"
            else:
                urgency = "LOW"
            
            # Минимальная партия (MOQ)
            moq = 5  # По умолчанию
            
            # Финальное количество с учетом MOQ
            final_quantity = max(recommended_quantity, moq) if recommended_quantity > 0 else 0
            
            forecast_item = ForecastItem(
                sku=sku,
                avg_daily_sales=round(avg_daily_sales, 2),
                current_stock=current_stock,
                days_until_stockout=round(days_until_stockout, 1),
                recommended_quantity=int(final_quantity),
                moq=moq,
                forecast_quality=forecast_quality,
                confidence=confidence,
                urgency=urgency
            )
            
            forecast_items.append(forecast_item)
        
        logger.info(f"Рассчитан прогноз для {len(forecast_items)} SKU")
        return forecast_items
    
    def analyze_seasonality(self, sales_data: List[SalesRecord]) -> SeasonalityData:
        """Анализирует сезонность продаж"""
        logger.info("Анализ сезонности продаж")
        
        if not sales_data:
            return SeasonalityData(
                daily_pattern=[],
                monthly_pattern=[],
                peak_day={'day': 'Пн', 'avg_sales': 0},
                peak_month={'month': 'Янв', 'avg_sales': 0}
            )
        
        # Группируем по дням недели
        daily_sales = {}
        for i in range(7):
            daily_sales[i] = []
        
        for sale in sales_data:
            day_of_week = sale.date.weekday()
            daily_sales[day_of_week].append(sale.quantity)
        
        # Рассчитываем средние продажи по дням недели
        daily_pattern = []
        day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        
        for day_num, quantities in daily_sales.items():
            avg_quantity = sum(quantities) / len(quantities) if quantities else 0
            daily_pattern.append({
                'day': day_names[day_num],
                'avg_sales': round(avg_quantity, 2),
                'count': len(quantities)
            })
        
        # Группируем по месяцам
        monthly_sales = {}
        for i in range(1, 13):
            monthly_sales[i] = []
        
        for sale in sales_data:
            month = sale.date.month
            monthly_sales[month].append(sale.quantity)
        
        # Рассчитываем средние продажи по месяцам
        monthly_pattern = []
        month_names = [
            'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
            'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'
        ]
        
        for month_num, quantities in monthly_sales.items():
            avg_quantity = sum(quantities) / len(quantities) if quantities else 0
            monthly_pattern.append({
                'month': month_names[month_num - 1],
                'avg_sales': round(avg_quantity, 2),
                'count': len(quantities)
            })
        
        # Находим пиковые дни и месяцы
        peak_day = max(daily_pattern, key=lambda x: x['avg_sales'])
        peak_month = max(monthly_pattern, key=lambda x: x['avg_sales'])
        
        return SeasonalityData(
            daily_pattern=daily_pattern,
            monthly_pattern=monthly_pattern,
            peak_day=peak_day,
            peak_month=peak_month
        )
    
    def generate_recommendations(self, forecast_items: List[ForecastItem]) -> List[Dict[str, Any]]:
        """Генерирует рекомендации на основе прогноза"""
        recommendations = []
        
        # Анализируем критические позиции
        critical_items = [item for item in forecast_items if item.urgency == "HIGH"]
        if critical_items:
            recommendations.append({
                'type': 'CRITICAL_PURCHASE',
                'priority': 'HIGH',
                'message': f"Срочно закупить {len(critical_items)} позиций",
                'action': 'Немедленно оформить заказы',
                'affected_skus': len(critical_items)
            })
        
        # Анализируем товары с низким качеством прогноза
        low_quality_items = [item for item in forecast_items if item.forecast_quality in ["LOW_DATA", "NO_SALES"]]
        if low_quality_items:
            recommendations.append({
                'type': 'DATA_QUALITY',
                'priority': 'MEDIUM',
                'message': f"Улучшить качество данных для {len(low_quality_items)} SKU",
                'action': 'Собрать больше исторических данных',
                'affected_skus': len(low_quality_items)
            })
        
        # Анализируем товары с нулевой продажей
        zero_sales_items = [item for item in forecast_items if item.avg_daily_sales == 0]
        if zero_sales_items:
            recommendations.append({
                'type': 'ZERO_SALES',
                'priority': 'MEDIUM',
                'message': f"Проанализировать {len(zero_sales_items)} SKU с нулевой продажей",
                'action': 'Проверить актуальность товаров',
                'affected_skus': len(zero_sales_items)
            })
        
        return recommendations

# Инициализация калькулятора
forecast_calculator = ForecastCalculator()

# ============================================================================
# Эндпоинты
# ============================================================================

@app.post("/forecast/calculate", response_model=ForecastResponse)
@handle_service_error
async def calculate_forecast(
    request: ForecastRequest,
    redis_client: RedisClient = Depends(get_redis_client),
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Расчет прогноза закупок"""
    logger.info("Запрос на расчет прогноза закупок")
    
    # Проверяем кэш
    cache_key = f"forecast:calculate:{hash(str(request.dict()))}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем прогноз из кэша")
        return ForecastResponse(**cached_result)
    
    # Рассчитываем прогноз
    forecast_items = forecast_calculator.calculate_forecast(
        request.sales_data,
        request.stocks_data,
        request.days_forecast_short,
        request.days_forecast_long
    )
    
    # Анализируем сезонность
    seasonality = forecast_calculator.analyze_seasonality(request.sales_data)
    
    # Генерируем рекомендации
    recommendations = forecast_calculator.generate_recommendations(forecast_items)
    
    # Формируем аналитику
    analytics = {
        'total_skus': len(forecast_items),
        'skus_needing_purchase': len([item for item in forecast_items if item.recommended_quantity > 0]),
        'critical_skus': len([item for item in forecast_items if item.urgency == "HIGH"]),
        'total_recommended_quantity': sum(item.recommended_quantity for item in forecast_items),
        'avg_days_until_stockout': sum(item.days_until_stockout for item in forecast_items) / len(forecast_items) if forecast_items else 0,
        'seasonality': seasonality.dict()
    }
    
    # Формируем ответ
    response = ForecastResponse(
        success=True,
        forecast=forecast_items,
        analytics=analytics,
        recommendations=recommendations,
        total_items=len(forecast_items)
    )
    
    # Кэшируем результат
    redis_client.set(cache_key, response.dict(), ttl=1800)  # 30 минут
    
    # Отправляем событие о завершении расчета
    event = {
        'event_type': 'forecast_calculated',
        'service': 'forecast-service',
        'data': {
            'total_items': len(forecast_items),
            'timestamp': datetime.now().isoformat()
        }
    }
    
    rabbitmq_client.publish_message('forecast.calculate', event)
    
    return response

@app.get("/forecast/reports")
@handle_service_error
async def get_forecast_reports(
    limit: int = 100,
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение отчетов о прогнозах"""
    logger.info(f"Запрос отчетов о прогнозах: limit={limit}")
    
    # Проверяем кэш
    cache_key = f"forecast:reports:limit:{limit}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем отчеты из кэша")
        return cached_result
    
    # Получаем отчеты из БД
    query = """
        SELECT id, forecast_data, created_at, total_items
        FROM forecasts
        ORDER BY created_at DESC
        LIMIT :limit
    """
    
    reports_data = db_client.execute_query(query, {'limit': limit})
    
    # Кэшируем результат
    redis_client.set(cache_key, reports_data, ttl=600)  # 10 минут
    
    return reports_data

@app.get("/forecast/analytics")
@handle_service_error
async def get_forecast_analytics(
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение аналитики по прогнозам"""
    logger.info("Запрос аналитики по прогнозам")
    
    # Проверяем кэш
    cache_key = "forecast:analytics"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем аналитику из кэша")
        return cached_result
    
    # Получаем аналитику из БД
    query = """
        SELECT 
            COUNT(*) as total_forecasts,
            AVG(total_items) as avg_items_per_forecast,
            MAX(created_at) as last_forecast_date
        FROM forecasts
    """
    
    analytics_data = db_client.execute_query(query)
    
    if analytics_data:
        analytics = analytics_data[0]
    else:
        analytics = {
            'total_forecasts': 0,
            'avg_items_per_forecast': 0,
            'last_forecast_date': None
        }
    
    # Кэшируем результат
    redis_client.set(cache_key, analytics, ttl=300)  # 5 минут
    
    return analytics

@app.post("/forecast/export")
@handle_service_error
async def export_forecast(
    forecast_data: List[ForecastItem],
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client),
    format: str = "csv"
):
    """Экспорт прогноза"""
    logger.info(f"Запрос экспорта прогноза в формате {format}")
    
    # Отправляем задачу экспорта в очередь
    event = {
        'event_type': 'export_forecast',
        'service': 'forecast-service',
        'data': {
            'forecast_data': [item.dict() for item in forecast_data],
            'format': format,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    success = rabbitmq_client.publish_message('storage.export', event)
    
    if success:
        background_tasks.add_task(process_export, forecast_data, format)
        return BaseResponse(
            success=True,
            message=f"Экспорт прогноза в формате {format} запущен"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Ошибка отправки задачи экспорта"
        )

async def process_export(forecast_data: List[ForecastItem], format: str):
    """Обработка экспорта в фоновом режиме"""
    logger.info(f"Обработка экспорта в формате {format}")
    
    try:
        # Здесь будет логика экспорта
        # Пока просто логируем
        logger.info(f"Экспорт {len(forecast_data)} позиций в формате {format} завершен")
        
        # Отправляем уведомление
        notification_event = {
            'event_type': 'export_completed',
            'service': 'forecast-service',
            'data': {
                'message': f'Экспорт прогноза в формате {format} завершен',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        rabbitmq_client.publish_message('notifications.send', notification_event)
        
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        
        # Отправляем уведомление об ошибке
        error_event = {
            'event_type': 'export_error',
            'service': 'forecast-service',
            'data': {
                'message': f'Ошибка экспорта: {e}',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        rabbitmq_client.publish_message('notifications.send', error_event)

@app.get("/forecast/recommendations")
@handle_service_error
async def get_forecast_recommendations(
    redis_client: RedisClient = Depends(get_redis_client),
    db_client: DatabaseClient = Depends(get_db_client)
):
    """Получение рекомендаций по прогнозам"""
    logger.info("Запрос рекомендаций по прогнозам")
    
    # Проверяем кэш
    cache_key = "forecast:recommendations"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Возвращаем рекомендации из кэша")
        return cached_result
    
    # Получаем последний прогноз
    query = """
        SELECT forecast_data
        FROM forecasts
        ORDER BY created_at DESC
        LIMIT 1
    """
    
    forecast_result = db_client.execute_query(query)
    
    if forecast_result:
        # Здесь можно добавить логику генерации рекомендаций
        # Пока возвращаем базовые рекомендации
        recommendations = [
            {
                'type': 'GENERAL',
                'priority': 'MEDIUM',
                'message': 'Регулярно обновляйте данные о продажах',
                'action': 'Синхронизируйте данные с Ozon API'
            }
        ]
    else:
        recommendations = []
    
    # Кэшируем результат
    redis_client.set(cache_key, recommendations, ttl=1800)  # 30 минут
    
    return recommendations

# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "service": "forecast-service",
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
        port=8002,
        reload=True,
        log_level=config['log_level'].lower()
    ) 