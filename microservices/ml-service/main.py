import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

# Добавляем путь к shared модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    MLPredictionRequest, MLPredictionResponse, ModelTrainingRequest,
    ModelTrainingResponse, ModelEvaluationResponse, BaseResponse, ErrorResponse
)
from shared.utils import (
    get_config, setup_logging, RedisClient, RabbitMQClient,
    DatabaseClient, handle_service_error, ServiceException
)

# Импортируем новые ML модели
from ml_models import (
    LinearRegressionModel, RandomForestModel, SARIMAModel, EnsembleModel
)

# ============================================================================
# Конфигурация
# ============================================================================

config = get_config()
logger = setup_logging('ml-service', config['log_level'])

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
    logger.info("ML Service запускается...")
    yield
    # Shutdown
    logger.info("ML Service останавливается...")
    rabbitmq_client.close()

app = FastAPI(
    title="ML Service",
    description="Сервис машинного обучения для прогнозирования продаж",
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
# Классы моделей импортированы из ml_models.py
# ============================================================================

# ============================================================================
# Класс для управления моделями
# ============================================================================

class ModelManager:
    """Менеджер для управления ML моделями"""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.models = {
            'linear_regression': LinearRegressionModel(),
            'random_forest': RandomForestModel(),
            'sarima': SARIMAModel(),
            'ensemble': EnsembleModel()
        }
        self.models_cache_key = "ml:models"

    def save_model_info(self, model_info: Dict[str, Any]) -> bool:
        """Сохраняет информацию о модели в кэш"""
        try:
            self.redis_client.set(
                self.models_cache_key,
                json.dumps(model_info),
                ttl=3600 * 24  # 24 часа
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения информации о модели: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Получает информацию о моделях из кэша"""
        try:
            data = self.redis_client.get(self.models_cache_key)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Ошибка получения информации о моделях: {e}")
            return {}

    def train_models(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает все модели"""
        try:
            logger.info("Начало обучения всех моделей")
            
            results = {}
            
            # Обучаем каждую модель
            for name, model in self.models.items():
                try:
                    model_info = model.train(sales_data)
                    results[name] = model_info
                    logger.info(f"Модель {name} обучена успешно")
            except Exception as e:
                    logger.error(f"Ошибка обучения модели {name}: {e}")
                    results[name] = {'error': str(e)}
            
            # Сохраняем информацию о моделях
            self.save_model_info(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка обучения моделей: {e}")
            raise

    def make_predictions(self, features: List[Dict[str, Any]], 
                        sku: str = None, steps: int = 30) -> Dict[str, Any]:
        """Делает предсказания всеми моделями"""
        try:
            predictions = {}
            
            # Предсказания каждой модели
            for name, model in self.models.items():
                if model.is_trained:
                    try:
                        if name == 'sarima':
                    if sku:
                                pred = model.predict(sku, steps)
                            else:
                                pred = model.predict_all(steps)
                    else:
                            pred = model.predict(features)
                        predictions[name] = pred
                except Exception as e:
                        logger.error(f"Ошибка предсказания модели {name}: {e}")
                        predictions[name] = {'error': str(e)}
            
            return predictions
            
        except Exception as e:
            logger.error(f"Ошибка предсказаний: {e}")
            raise

    def get_model_status(self) -> Dict[str, Any]:
        """Получает статус всех моделей"""
        status = {}
        
        for name, model in self.models.items():
            status[name] = {
                'trained': model.is_trained,
                'last_trained': model.model_info.get('trained_at'),
                'metrics': model.model_info.get('metrics', {})
            }
            
            if name == 'sarima':
                status[name]['n_models'] = len(model.models) if hasattr(model, 'models') else 0
            elif name == 'ensemble':
                status[name]['trained_models'] = model.model_info.get('trained_models', [])
        
        return status

# ============================================================================
# Инициализация компонентов
# ============================================================================

model_manager = ModelManager(redis_client)

# ============================================================================
# Эндпоинты
# ============================================================================

@app.get("/health")
@handle_service_error
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "service": "ml-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": config['version']
    }

@app.post("/models/train", response_model=ModelTrainingResponse)
@handle_service_error
async def train_models(
    request: ModelTrainingRequest,
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Обучение ML моделей"""
    logger.info("Запрос на обучение моделей")

    try:
        # Обучаем модели
        results = model_manager.train_models(request.sales_data)

        # Отправляем событие в очередь
        event = {
            'event_type': 'models_trained',
            'service': 'ml-service',
            'data': {
                'models_trained': list(results.keys()),
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('ml.events', event)

        return ModelTrainingResponse(
            success=True,
            message="Модели успешно обучены",
            results=results
        )

    except Exception as e:
        logger.error(f"Ошибка обучения моделей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/models/predict", response_model=MLPredictionResponse)
@handle_service_error
async def make_predictions(
    request: MLPredictionRequest,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Получение предсказаний от ML моделей"""
    logger.info("Запрос на получение предсказаний")

    try:
        predictions = model_manager.make_predictions(
            request.features,
            request.sku,
            request.steps
        )

        # Отправляем событие в очередь
        event = {
            'event_type': 'predictions_made',
            'service': 'ml-service',
            'data': {
                'models_used': list(predictions.keys()),
                'predictions_count': len(predictions),
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('ml.events', event)

        return MLPredictionResponse(
            success=True,
            predictions=predictions,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Ошибка получения предсказаний: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/models/evaluate")
@handle_service_error
async def evaluate_models(test_data: List[Dict[str, Any]]):
    """Оценка качества моделей"""
    logger.info("Запрос на оценку моделей")

    try:
        results = {}

        # Оцениваем линейную регрессию
        if model_manager.linear_model.is_trained:
            try:
                linear_eval = model_manager.linear_model.evaluate(test_data)
                results['linear_regression'] = linear_eval
            except Exception as e:
                logger.error(f"Ошибка оценки линейной регрессии: {e}")
                results['linear_regression'] = {'error': str(e)}

        return {
            'success': True,
            'evaluation': results,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка оценки моделей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models/info")
@handle_service_error
async def get_models_info():
    """Получение информации о моделях"""
    logger.info("Запрос информации о моделях")

    model_info = model_manager.get_model_info()

    return {
        'success': True,
        'models_info': model_info,
        'linear_model_trained': model_manager.linear_model.is_trained,
        'sarima_model_trained': model_manager.sarima_model.is_trained,
        'timestamp': datetime.now().isoformat()
    }

@app.get("/models/status")
@handle_service_error
async def get_models_status():
    """Получение статуса моделей"""
    logger.info("Запрос статуса моделей")

    status = model_manager.get_model_status()

    return {
        'success': True,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }

@app.post("/models/retrain")
@handle_service_error
async def retrain_models(
    sales_data: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client)
):
    """Переобучение моделей"""
    logger.info("Запрос на переобучение моделей")

    try:
        # Переобучаем модели
        results = model_manager.train_models(sales_data)

        # Отправляем событие в очередь
        event = {
            'event_type': 'models_retrained',
            'service': 'ml-service',
            'data': {
                'models_retrained': list(results.keys()),
                'timestamp': datetime.now().isoformat()
            }
        }

        rabbitmq_client.publish_message('ml.events', event)

        return {
            'success': True,
            'message': "Модели успешно переобучены",
            'results': results
        }

    except Exception as e:
        logger.error(f"Ошибка переобучения моделей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Фоновые задачи
# ============================================================================

async def periodic_model_retraining():
    """Периодическое переобучение моделей"""
    try:
        # Здесь будет логика автоматического переобучения
        logger.info("Периодическое переобучение моделей завершено")
    except Exception as e:
        logger.error(f"Ошибка периодического переобучения: {e}")

# ============================================================================
# Обработчик событий из очереди
# ============================================================================

def handle_ml_event(ch, method, properties, body):
    """Обработчик событий из очереди"""
    try:
        event = json.loads(body)
        event_type = event.get('event_type')
        
        logger.info(f"Получено событие ML: {event_type}")
        
        if event_type == 'sales_data_updated':
            # Обработка обновления данных о продажах
            data = event.get('data', {})
            logger.info(f"Обновлены данные о продажах: {data.get('records_count')} записей")
            
        elif event_type == 'forecast_requested':
            # Обработка запроса прогноза
            data = event.get('data', {})
            logger.info(f"Запрошен прогноз для {data.get('sku_count')} SKU")
            
    except Exception as e:
        logger.error(f"Ошибка обработки события ML: {e}")

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
        log_level=config['log_level'].lower()
    ) 