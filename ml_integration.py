"""
Интеграция ML-моделей с основным прогнозированием
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import logging
import requests
import json
from config import logger

class MLForecastIntegration:
    """Интеграция ML-моделей с прогнозированием закупок"""
    
    def __init__(self, ml_service_url: str = "http://localhost:8006"):
        self.ml_service_url = ml_service_url
        self.logger = logger
        
    def prepare_ml_features(self, sales_df: pd.DataFrame, forecast_days: int = 30) -> List[Dict[str, Any]]:
        """Подготавливает признаки для ML-моделей"""
        try:
            if sales_df.empty:
                return []
            
            # Создаем будущие даты для прогнозирования
            last_date = sales_df['date'].max()
            future_dates = pd.date_range(
                start=last_date + timedelta(days=1),
                periods=forecast_days,
                freq='D'
            )
            
            # Создаем признаки для каждой будущей даты
            features = []
            
            for date in future_dates:
                feature_dict = {
                    'date': date.isoformat(),
                    'day_of_week': date.dayofweek,
                    'month': date.month,
                    'day_of_month': date.day,
                    'is_weekend': 1 if date.dayofweek in [5, 6] else 0,
                    'is_month_start': 1 if date.is_month_start else 0,
                    'is_month_end': 1 if date.is_month_end else 0,
                    'quarter': date.quarter,
                    'week_of_year': date.isocalendar().week
                }
                
                # Добавляем SKU если есть
                if 'sku' in sales_df.columns:
                    for sku in sales_df['sku'].unique():
                        sku_feature = feature_dict.copy()
                        sku_feature['sku'] = sku
                        features.append(sku_feature)
                else:
                    features.append(feature_dict)
            
            self.logger.info(f"Подготовлено {len(features)} признаков для ML-прогнозирования")
            return features
            
        except Exception as e:
            self.logger.error(f"Ошибка подготовки ML-признаков: {e}")
            return []
    
    def train_ml_models(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает ML-модели"""
        try:
            self.logger.info("Обучение ML-моделей...")
            
            # Отправляем запрос на обучение
            response = requests.post(
                f"{self.ml_service_url}/models/train",
                json={'sales_data': sales_data},
                timeout=300  # 5 минут на обучение
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info("ML-модели успешно обучены")
                return result
            else:
                self.logger.error(f"Ошибка обучения ML-моделей: {response.text}")
                return {'error': response.text}
                
        except Exception as e:
            self.logger.error(f"Ошибка обучения ML-моделей: {e}")
            return {'error': str(e)}
    
    def get_ml_predictions(self, features: List[Dict[str, Any]], 
                          sku: str = None, steps: int = 30) -> Dict[str, Any]:
        """Получает предсказания от ML-моделей"""
        try:
            self.logger.info("Получение ML-предсказаний...")
            
            # Отправляем запрос на предсказание
            response = requests.post(
                f"{self.ml_service_url}/models/predict",
                json={
                    'features': features,
                    'sku': sku,
                    'steps': steps
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info("ML-предсказания получены успешно")
                return result
            else:
                self.logger.error(f"Ошибка получения ML-предсказаний: {response.text}")
                return {'error': response.text}
                
        except Exception as e:
            self.logger.error(f"Ошибка получения ML-предсказаний: {e}")
            return {'error': str(e)}
    
    def get_ml_model_status(self) -> Dict[str, Any]:
        """Получает статус ML-моделей"""
        try:
            response = requests.get(
                f"{self.ml_service_url}/models/status",
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': response.text}
                
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса ML-моделей: {e}")
            return {'error': str(e)}
    
    def enhance_forecast_with_ml(self, forecast_df: pd.DataFrame, 
                                sales_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Улучшает прогноз с помощью ML-моделей"""
        try:
            self.logger.info("Улучшение прогноза с помощью ML-моделей...")
            
            if forecast_df.empty:
                return forecast_df
            
            # Получаем ML-предсказания
            features = self.prepare_ml_features(
                pd.DataFrame(sales_data), 
                forecast_days=30
            )
            
            if not features:
                self.logger.warning("Не удалось подготовить признаки для ML")
                return forecast_df
            
            ml_predictions = self.get_ml_predictions(features)
            
            if 'error' in ml_predictions:
                self.logger.warning(f"Ошибка получения ML-предсказаний: {ml_predictions['error']}")
                return forecast_df
            
            # Улучшаем прогноз с помощью ML
            enhanced_forecast = forecast_df.copy()
            
            # Добавляем ML-предсказания если они есть
            if 'predictions' in ml_predictions:
                predictions = ml_predictions['predictions']
                
                # Используем ансамбль если доступен
                if 'ensemble' in predictions and isinstance(predictions['ensemble'], list):
                    ensemble_pred = predictions['ensemble']
                    
                    # Обновляем среднюю дневную продажу на основе ML-предсказаний
                    for i, row in enhanced_forecast.iterrows():
                        sku = row['sku']
                        
                        # Находим соответствующие предсказания для SKU
                        sku_predictions = []
                        for j, feature in enumerate(features):
                            if feature.get('sku') == sku and j < len(ensemble_pred):
                                sku_predictions.append(ensemble_pred[j])
                        
                        if sku_predictions:
                            # Вычисляем новую среднюю продажу на основе ML
                            ml_avg_sales = np.mean(sku_predictions)
                            
                            # Комбинируем с существующим прогнозом (70% ML + 30% базовый)
                            original_avg = row['avg_daily_sales']
                            enhanced_forecast.loc[i, 'avg_daily_sales'] = (
                                0.7 * ml_avg_sales + 0.3 * original_avg
                            )
                            
                            # Обновляем качество прогноза
                            enhanced_forecast.loc[i, 'forecast_quality'] = 'ML_ENHANCED'
                
                # Также используем линейную регрессию если доступна
                elif 'linear_regression' in predictions and isinstance(predictions['linear_regression'], list):
                    linear_pred = predictions['linear_regression']
                    
                    for i, row in enhanced_forecast.iterrows():
                        sku = row['sku']
                        
                        sku_predictions = []
                        for j, feature in enumerate(features):
                            if feature.get('sku') == sku and j < len(linear_pred):
                                sku_predictions.append(linear_pred[j])
                        
                        if sku_predictions:
                            ml_avg_sales = np.mean(sku_predictions)
                            original_avg = row['avg_daily_sales']
                            enhanced_forecast.loc[i, 'avg_daily_sales'] = (
                                0.6 * ml_avg_sales + 0.4 * original_avg
                            )
                            enhanced_forecast.loc[i, 'forecast_quality'] = 'ML_ENHANCED'
            
            # Пересчитываем дни до исчерпания и рекомендуемое количество
            enhanced_forecast['days_until_stockout'] = np.where(
                enhanced_forecast['avg_daily_sales'] > 0,
                enhanced_forecast['available_stock'] / enhanced_forecast['avg_daily_sales'],
                float('inf')
            )
            
            enhanced_forecast['needs_purchase_short'] = enhanced_forecast['days_until_stockout'] < 40
            enhanced_forecast['needs_purchase_long'] = enhanced_forecast['days_until_stockout'] < 120
            
            enhanced_forecast['recommended_quantity'] = np.where(
                enhanced_forecast['needs_purchase_short'],
                np.maximum(
                    (120 - enhanced_forecast['days_until_stockout']) * enhanced_forecast['avg_daily_sales'],
                    enhanced_forecast['avg_daily_sales'] * 40
                ),
                0
            )
            
            # Применяем минимальные партии
            from config import get_moq_for_sku
            enhanced_forecast['moq'] = enhanced_forecast['sku'].apply(get_moq_for_sku)
            enhanced_forecast['final_order_quantity'] = np.where(
                enhanced_forecast['recommended_quantity'] > 0,
                np.maximum(enhanced_forecast['recommended_quantity'], enhanced_forecast['moq']),
                0
            )
            
            enhanced_forecast['final_order_quantity'] = enhanced_forecast['final_order_quantity'].round().astype(int)
            
            self.logger.info(f"Прогноз улучшен с помощью ML для {len(enhanced_forecast)} SKU")
            return enhanced_forecast
            
        except Exception as e:
            self.logger.error(f"Ошибка улучшения прогноза с помощью ML: {e}")
            return forecast_df
    
    def compare_forecast_methods(self, sales_data: List[Dict[str, Any]], 
                               stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Сравнивает различные методы прогнозирования"""
        try:
            self.logger.info("Сравнение методов прогнозирования...")
            
            from forecast import PurchaseForecast
            
            # Базовый прогноз
            forecast_service = PurchaseForecast()
            sales_df = forecast_service.prepare_sales_data(sales_data)
            stocks_df = forecast_service.prepare_stocks_data(stocks_data)
            
            base_forecast = forecast_service.calculate_forecast(sales_df, stocks_df)
            
            # ML-улучшенный прогноз
            ml_enhanced_forecast = self.enhance_forecast_with_ml(base_forecast, sales_data)
            
            # Сравниваем результаты
            comparison = {
                'base_forecast': {
                    'total_skus': len(base_forecast),
                    'skus_needing_purchase': len(base_forecast[base_forecast['needs_purchase_short']]),
                    'total_quantity': int(base_forecast['final_order_quantity'].sum()),
                    'avg_days_until_stockout': float(base_forecast['days_until_stockout'].mean())
                },
                'ml_enhanced_forecast': {
                    'total_skus': len(ml_enhanced_forecast),
                    'skus_needing_purchase': len(ml_enhanced_forecast[ml_enhanced_forecast['needs_purchase_short']]),
                    'total_quantity': int(ml_enhanced_forecast['final_order_quantity'].sum()),
                    'avg_days_until_stockout': float(ml_enhanced_forecast['days_until_stockout'].mean())
                },
                'improvements': {
                    'quantity_difference': int(ml_enhanced_forecast['final_order_quantity'].sum() - 
                                             base_forecast['final_order_quantity'].sum()),
                    'purchase_items_difference': len(ml_enhanced_forecast[ml_enhanced_forecast['needs_purchase_short']]) - 
                                               len(base_forecast[base_forecast['needs_purchase_short']])
                }
            }
            
            self.logger.info("Сравнение методов прогнозирования завершено")
            return comparison
            
        except Exception as e:
            self.logger.error(f"Ошибка сравнения методов прогнозирования: {e}")
            return {'error': str(e)}
    
    def generate_ml_forecast_report(self, sales_data: List[Dict[str, Any]], 
                                  stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерирует отчет с ML-прогнозом"""
        try:
            self.logger.info("Генерация ML-отчета о прогнозе...")
            
            # Получаем статус ML-моделей
            ml_status = self.get_ml_model_status()
            
            # Сравниваем методы прогнозирования
            comparison = self.compare_forecast_methods(sales_data, stocks_data)
            
            # Создаем отчет
            report = {
                'timestamp': datetime.now().isoformat(),
                'ml_models_status': ml_status,
                'forecast_comparison': comparison,
                'recommendations': []
            }
            
            # Добавляем рекомендации на основе сравнения
            if 'improvements' in comparison:
                improvements = comparison['improvements']
                
                if improvements['quantity_difference'] > 0:
                    report['recommendations'].append({
                        'type': 'QUANTITY_INCREASE',
                        'message': f"ML-модели рекомендуют увеличить закупки на {improvements['quantity_difference']} шт",
                        'priority': 'MEDIUM'
                    })
                
                if improvements['purchase_items_difference'] > 0:
                    report['recommendations'].append({
                        'type': 'MORE_ITEMS',
                        'message': f"ML-модели выявили {improvements['purchase_items_difference']} дополнительных позиций для закупки",
                        'priority': 'HIGH'
                    })
            
            # Проверяем качество ML-моделей
            if 'status' in ml_status:
                status = ml_status['status']
                trained_models = [name for name, info in status.items() 
                                if info.get('trained', False)]
                
                if len(trained_models) < 2:
                    report['recommendations'].append({
                        'type': 'MODEL_TRAINING',
                        'message': f"Рекомендуется обучить больше ML-моделей. Обучено: {len(trained_models)}",
                        'priority': 'LOW'
                    })
            
            self.logger.info("ML-отчет о прогнозе сгенерирован")
            return report
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации ML-отчета: {e}")
            return {'error': str(e)}

def main():
    """Демонстрация интеграции ML с прогнозированием"""
    # Пример использования
    ml_integration = MLForecastIntegration()
    
    # Проверяем статус ML-моделей
    status = ml_integration.get_ml_model_status()
    print("Статус ML-моделей:", json.dumps(status, indent=2, ensure_ascii=False))
    
    # Здесь можно добавить тестовые данные и демонстрацию работы

if __name__ == "__main__":
    main() 