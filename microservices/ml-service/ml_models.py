"""
Расширенные ML-модели для прогнозирования продаж
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import logging
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split, cross_val_score
import warnings
warnings.filterwarnings('ignore')

# Для временных рядов
try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.seasonal import seasonal_decompose
    SARIMA_AVAILABLE = True
except ImportError:
    SARIMA_AVAILABLE = False
    print("SARIMA недоступен. Установите statsmodels для полной функциональности.")

logger = logging.getLogger(__name__)

class BaseMLModel:
    """Базовый класс для ML моделей"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.is_trained = False
        self.model_info = {}
        self.feature_names = []
        self.scaler = None
        
    def prepare_features(self, sales_data: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Подготавливает признаки для модели"""
        raise NotImplementedError
        
    def train(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает модель"""
        raise NotImplementedError
        
    def predict(self, features: List[Dict[str, Any]]) -> List[float]:
        """Делает предсказания"""
        raise NotImplementedError
        
    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает качество модели"""
        raise NotImplementedError

class LinearRegressionModel(BaseMLModel):
    """Модель линейной регрессии с расширенными признаками"""
    
    def __init__(self):
        super().__init__("linear_regression")
        self.model = LinearRegression()
        self.scaler = StandardScaler()
        
    def prepare_features(self, sales_data: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Подготавливает признаки для линейной регрессии"""
        try:
            df = pd.DataFrame(sales_data)
            
            if df.empty:
                raise ValueError("Нет данных для подготовки признаков")

            # Создаем признаки
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['month'] = df['date'].dt.month
            df['day_of_month'] = df['date'].dt.day
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            df['is_month_start'] = df['date'].dt.is_month_start.astype(int)
            df['is_month_end'] = df['date'].dt.is_month_end.astype(int)
            
            # Лаговые признаки
            for lag in [1, 3, 7, 14]:
                df[f'sales_lag_{lag}'] = df.groupby('sku')['quantity'].shift(lag)
            
            # Скользящие средние
            for window in [3, 7, 14, 30]:
                df[f'sales_ma_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).mean().reset_index(0, drop=True)
            
            # Скользящие стандартные отклонения
            for window in [7, 14]:
                df[f'sales_std_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).std().reset_index(0, drop=True)
            
            # Признаки тренда
            df['sales_trend'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Сезонные признаки
            df['quarter'] = df['date'].dt.quarter
            df['week_of_year'] = df['date'].dt.isocalendar().week
            
            # Признаки волатильности
            df['sales_volatility'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.std(x) if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Выбираем числовые признаки
            feature_columns = [
                'day_of_week', 'month', 'day_of_month', 'is_weekend',
                'is_month_start', 'is_month_end', 'quarter', 'week_of_year',
                'sales_lag_1', 'sales_lag_3', 'sales_lag_7', 'sales_lag_14',
                'sales_ma_3', 'sales_ma_7', 'sales_ma_14', 'sales_ma_30',
                'sales_std_7', 'sales_std_14', 'sales_trend', 'sales_volatility'
            ]
            
            # Удаляем строки с NaN значениями
            df_clean = df.dropna(subset=feature_columns)
            
            if df_clean.empty:
                raise ValueError("После очистки данных не осталось записей")
            
            X = df_clean[feature_columns].values
            y = df_clean['quantity'].values
            
            self.feature_names = feature_columns
            
            logger.info(f"Подготовлено {len(X)} образцов с {len(feature_columns)} признаками")
            return X, y
            
        except Exception as e:
            logger.error(f"Ошибка подготовки признаков: {e}")
            raise

    def train(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает модель линейной регрессии"""
        try:
            logger.info("Начало обучения модели линейной регрессии")
            
            # Подготавливаем данные
            X, y = self.prepare_features(sales_data)
            
            # Разделяем на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Масштабируем признаки
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Обучаем модель
            self.model.fit(X_train_scaled, y_train)
            
            # Делаем предсказания
            y_train_pred = self.model.predict(X_train_scaled)
            y_test_pred = self.model.predict(X_test_scaled)
            
            # Вычисляем метрики
            train_mae = mean_absolute_error(y_train, y_train_pred)
            train_mse = mean_squared_error(y_train, y_train_pred)
            train_rmse = np.sqrt(train_mse)
            train_r2 = r2_score(y_train, y_train_pred)
            
            test_mae = mean_absolute_error(y_test, y_test_pred)
            test_mse = mean_squared_error(y_test, y_test_pred)
            test_rmse = np.sqrt(test_mse)
            test_r2 = r2_score(y_test, y_test_pred)
            
            # Кросс-валидация
            cv_scores = cross_val_score(
                self.model, X_train_scaled, y_train, 
                cv=5, scoring='r2'
            )
            
            # Сохраняем информацию о модели
            self.model_info = {
                'model_type': 'linear_regression',
                'trained_at': datetime.now().isoformat(),
                'n_samples': len(X),
                'n_features': len(self.feature_names),
                'feature_names': self.feature_names,
                'train_metrics': {
                    'mae': float(train_mae),
                    'mse': float(train_mse),
                    'rmse': float(train_rmse),
                    'r2': float(train_r2)
                },
                'test_metrics': {
                    'mae': float(test_mae),
                    'mse': float(test_mse),
                    'rmse': float(test_rmse),
                    'r2': float(test_r2)
                },
                'cv_scores': cv_scores.tolist(),
                'cv_mean': float(cv_scores.mean()),
                'cv_std': float(cv_scores.std()),
                'coefficients': self.model.coef_.tolist(),
                'intercept': float(self.model.intercept_)
            }
            
            self.is_trained = True
            
            logger.info(f"Модель обучена. Тест R² = {test_r2:.4f}, RMSE = {test_rmse:.4f}")
            
            return self.model_info
            
        except Exception as e:
            logger.error(f"Ошибка обучения модели: {e}")
            raise

    def predict(self, features: List[Dict[str, Any]]) -> List[float]:
        """Делает предсказания"""
        try:
            if not self.is_trained:
                raise ValueError("Модель не обучена")
            
            # Подготавливаем признаки для предсказания
            df = pd.DataFrame(features)
            
            # Создаем те же признаки, что и при обучении
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['month'] = df['date'].dt.month
            df['day_of_month'] = df['date'].dt.day
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            df['is_month_start'] = df['date'].dt.is_month_start.astype(int)
            df['is_month_end'] = df['date'].dt.is_month_end.astype(int)
            df['quarter'] = df['date'].dt.quarter
            df['week_of_year'] = df['date'].dt.isocalendar().week
            
            # Лаговые признаки
            for lag in [1, 3, 7, 14]:
                df[f'sales_lag_{lag}'] = df.groupby('sku')['quantity'].shift(lag)
            
            # Скользящие средние
            for window in [3, 7, 14, 30]:
                df[f'sales_ma_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).mean().reset_index(0, drop=True)
            
            # Скользящие стандартные отклонения
            for window in [7, 14]:
                df[f'sales_std_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).std().reset_index(0, drop=True)
            
            # Признаки тренда
            df['sales_trend'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Признаки волатильности
            df['sales_volatility'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.std(x) if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Выбираем признаки
            X = df[self.feature_names].fillna(0).values
            
            # Масштабируем
            X_scaled = self.scaler.transform(X)
            
            # Делаем предсказания
            predictions = self.model.predict(X_scaled)
            
            logger.info(f"Сделано {len(predictions)} предсказаний")
            return predictions.tolist()
            
        except Exception as e:
            logger.error(f"Ошибка предсказания: {e}")
            raise

    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает качество модели"""
        try:
            if not self.is_trained:
                raise ValueError("Модель не обучена")
            
            # Подготавливаем тестовые данные
            X_test, y_test = self.prepare_features(test_data)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Делаем предсказания
            y_pred = self.model.predict(X_test_scaled)
            
            # Вычисляем метрики
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            evaluation = {
                'model_type': 'linear_regression',
                'evaluated_at': datetime.now().isoformat(),
                'n_test_samples': len(X_test),
                'metrics': {
                    'mae': float(mae),
                    'mse': float(mse),
                    'rmse': float(rmse),
                    'r2': float(r2)
                },
                'predictions': y_pred.tolist(),
                'actual': y_test.tolist()
            }
            
            logger.info(f"Оценка модели: R² = {r2:.4f}, RMSE = {rmse:.4f}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Ошибка оценки модели: {e}")
            raise

class RandomForestModel(BaseMLModel):
    """Модель случайного леса для прогнозирования продаж"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10):
        super().__init__("random_forest")
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        )
        self.scaler = StandardScaler()
        
    def prepare_features(self, sales_data: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Подготавливает признаки для случайного леса"""
        # Используем ту же подготовку признаков, что и для линейной регрессии
        return LinearRegressionModel().prepare_features(sales_data)
        
    def train(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает модель случайного леса"""
        try:
            logger.info("Начало обучения модели случайного леса")
            
            # Подготавливаем данные
            X, y = self.prepare_features(sales_data)
            
            # Разделяем на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Масштабируем признаки
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Обучаем модель
            self.model.fit(X_train_scaled, y_train)
            
            # Делаем предсказания
            y_train_pred = self.model.predict(X_train_scaled)
            y_test_pred = self.model.predict(X_test_scaled)
            
            # Вычисляем метрики
            train_mae = mean_absolute_error(y_train, y_train_pred)
            train_mse = mean_squared_error(y_train, y_train_pred)
            train_rmse = np.sqrt(train_mse)
            train_r2 = r2_score(y_train, y_train_pred)
            
            test_mae = mean_absolute_error(y_test, y_test_pred)
            test_mse = mean_squared_error(y_test, y_test_pred)
            test_rmse = np.sqrt(test_mse)
            test_r2 = r2_score(y_test, y_test_pred)
            
            # Кросс-валидация
            cv_scores = cross_val_score(
                self.model, X_train_scaled, y_train, 
                cv=5, scoring='r2'
            )
            
            # Важность признаков
            feature_importance = dict(zip(
                self.feature_names, 
                self.model.feature_importances_
            ))
            
            # Сохраняем информацию о модели
            self.model_info = {
                'model_type': 'random_forest',
                'trained_at': datetime.now().isoformat(),
                'n_samples': len(X),
                'n_features': len(self.feature_names),
                'feature_names': self.feature_names,
                'train_metrics': {
                    'mae': float(train_mae),
                    'mse': float(train_mse),
                    'rmse': float(train_rmse),
                    'r2': float(train_r2)
                },
                'test_metrics': {
                    'mae': float(test_mae),
                    'mse': float(test_mse),
                    'rmse': float(test_rmse),
                    'r2': float(test_r2)
                },
                'cv_scores': cv_scores.tolist(),
                'cv_mean': float(cv_scores.mean()),
                'cv_std': float(cv_scores.std()),
                'feature_importance': feature_importance,
                'n_estimators': self.model.n_estimators,
                'max_depth': self.model.max_depth
            }
            
            self.is_trained = True
            
            logger.info(f"Модель обучена. Тест R² = {test_r2:.4f}, RMSE = {test_rmse:.4f}")
            
            return self.model_info
            
        except Exception as e:
            logger.error(f"Ошибка обучения модели: {e}")
            raise

    def predict(self, features: List[Dict[str, Any]]) -> List[float]:
        """Делает предсказания"""
        try:
            if not self.is_trained:
                raise ValueError("Модель не обучена")
            
            # Подготавливаем признаки для предсказания
            df = pd.DataFrame(features)
            
            # Создаем те же признаки, что и при обучении
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['month'] = df['date'].dt.month
            df['day_of_month'] = df['date'].dt.day
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            df['is_month_start'] = df['date'].dt.is_month_start.astype(int)
            df['is_month_end'] = df['date'].dt.is_month_end.astype(int)
            df['quarter'] = df['date'].dt.quarter
            df['week_of_year'] = df['date'].dt.isocalendar().week
            
            # Лаговые признаки
            for lag in [1, 3, 7, 14]:
                df[f'sales_lag_{lag}'] = df.groupby('sku')['quantity'].shift(lag)
            
            # Скользящие средние
            for window in [3, 7, 14, 30]:
                df[f'sales_ma_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).mean().reset_index(0, drop=True)
            
            # Скользящие стандартные отклонения
            for window in [7, 14]:
                df[f'sales_std_{window}'] = df.groupby('sku')['quantity'].rolling(
                    window=window, min_periods=1
                ).std().reset_index(0, drop=True)
            
            # Признаки тренда
            df['sales_trend'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Признаки волатильности
            df['sales_volatility'] = df.groupby('sku')['quantity'].rolling(
                window=7, min_periods=1
            ).apply(
                lambda x: np.std(x) if len(x) > 1 else 0
            ).reset_index(0, drop=True)
            
            # Выбираем признаки
            X = df[self.feature_names].fillna(0).values
            
            # Масштабируем
            X_scaled = self.scaler.transform(X)
            
            # Делаем предсказания
            predictions = self.model.predict(X_scaled)
            
            logger.info(f"Сделано {len(predictions)} предсказаний")
            return predictions.tolist()
            
        except Exception as e:
            logger.error(f"Ошибка предсказания: {e}")
            raise

    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает качество модели"""
        try:
            if not self.is_trained:
                raise ValueError("Модель не обучена")
            
            # Подготавливаем тестовые данные
            X_test, y_test = self.prepare_features(test_data)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Делаем предсказания
            y_pred = self.model.predict(X_test_scaled)
            
            # Вычисляем метрики
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            evaluation = {
                'model_type': 'random_forest',
                'evaluated_at': datetime.now().isoformat(),
                'n_test_samples': len(X_test),
                'metrics': {
                    'mae': float(mae),
                    'mse': float(mse),
                    'rmse': float(rmse),
                    'r2': float(r2)
                },
                'predictions': y_pred.tolist(),
                'actual': y_test.tolist()
            }
            
            logger.info(f"Оценка модели: R² = {r2:.4f}, RMSE = {rmse:.4f}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Ошибка оценки модели: {e}")
            raise

class SARIMAModel(BaseMLModel):
    """Модель SARIMA для временных рядов"""
    
    def __init__(self, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7)):
        super().__init__("sarima")
        self.order = order
        self.seasonal_order = seasonal_order
        self.models = {}  # Модели для каждого SKU
        self.is_trained = False
        self.model_info = {}
        
        if not SARIMA_AVAILABLE:
            logger.warning("SARIMA недоступен. Установите statsmodels для полной функциональности.")

    def prepare_time_series(self, sales_data: List[Dict[str, Any]]) -> Dict[str, pd.Series]:
        """Подготавливает временные ряды для каждого SKU"""
        try:
            df = pd.DataFrame(sales_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Группируем по SKU и дате
            time_series = {}
            
            for sku in df['sku'].unique():
                sku_data = df[df['sku'] == sku].copy()
                sku_data = sku_data.set_index('date')['quantity'].resample('D').sum().fillna(0)
                
                if len(sku_data) >= 30:  # Минимум 30 дней данных
                    time_series[sku] = sku_data
            
            logger.info(f"Подготовлено {len(time_series)} временных рядов")
            return time_series
            
        except Exception as e:
            logger.error(f"Ошибка подготовки временных рядов: {e}")
            raise

    def train(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает SARIMA модели для каждого SKU"""
        try:
            if not SARIMA_AVAILABLE:
                raise ValueError("SARIMA недоступен. Установите statsmodels.")
                
            logger.info("Начало обучения SARIMA моделей")
            
            # Подготавливаем временные ряды
            time_series = self.prepare_time_series(sales_data)
            
            if not time_series:
                raise ValueError("Нет данных для обучения SARIMA моделей")
            
            # Обучаем модели для каждого SKU
            trained_models = {}
            metrics_summary = []
            
            for sku, series in time_series.items():
                try:
                    # Используем ARIMA для демонстрации
                    model = ARIMA(series, order=self.order)
                    fitted_model = model.fit()
                    
                    trained_models[sku] = fitted_model
                    
                    # Вычисляем метрики
                    predictions = fitted_model.forecast(steps=7)
                    actual = series.tail(7)
                    
                    if len(actual) > 0:
                        mae = mean_absolute_error(actual, predictions[:len(actual)])
                        mse = mean_squared_error(actual, predictions[:len(actual)])
                        rmse = np.sqrt(mse)
                        
                        metrics_summary.append({
                            'sku': sku,
                            'mae': float(mae),
                            'mse': float(mse),
                            'rmse': float(rmse),
                            'aic': float(fitted_model.aic),
                            'bic': float(fitted_model.bic)
                        })
                    
                    logger.info(f"Обучена SARIMA модель для SKU {sku}")
                    
                except Exception as e:
                    logger.warning(f"Ошибка обучения SARIMA для SKU {sku}: {e}")
                    continue
            
            self.models = trained_models
            
            # Вычисляем общие метрики
            if metrics_summary:
                avg_mae = np.mean([m['mae'] for m in metrics_summary])
                avg_rmse = np.mean([m['rmse'] for m in metrics_summary])
                avg_aic = np.mean([m['aic'] for m in metrics_summary])
            else:
                avg_mae = avg_rmse = avg_aic = 0
            
            self.model_info = {
                'model_type': 'sarima',
                'trained_at': datetime.now().isoformat(),
                'n_models': len(trained_models),
                'order': self.order,
                'seasonal_order': self.seasonal_order,
                'metrics': {
                    'avg_mae': float(avg_mae),
                    'avg_rmse': float(avg_rmse),
                    'avg_aic': float(avg_aic)
                },
                'models_summary': metrics_summary
            }
            
            self.is_trained = True
            
            logger.info(f"Обучено {len(trained_models)} SARIMA моделей")
            return self.model_info
            
        except Exception as e:
            logger.error(f"Ошибка обучения SARIMA моделей: {e}")
            raise

    def predict(self, sku: str, steps: int = 30) -> List[float]:
        """Делает предсказания для конкретного SKU"""
        try:
            if not self.is_trained or sku not in self.models:
                raise ValueError(f"SARIMA модель для SKU {sku} не обучена")
            
            model = self.models[sku]
            predictions = model.forecast(steps=steps)
            
            logger.info(f"Сделано {len(predictions)} предсказаний для SKU {sku}")
            return predictions.tolist()
            
        except Exception as e:
            logger.error(f"Ошибка предсказания SARIMA для SKU {sku}: {e}")
            raise

    def predict_all(self, steps: int = 30) -> Dict[str, List[float]]:
        """Делает предсказания для всех SKU"""
        try:
            if not self.is_trained:
                raise ValueError("SARIMA модели не обучены")
            
            predictions = {}
            
            for sku in self.models.keys():
                try:
                    pred = self.predict(sku, steps)
                    predictions[sku] = pred
                except Exception as e:
                    logger.warning(f"Ошибка предсказания для SKU {sku}: {e}")
                    continue
            
            logger.info(f"Сделаны предсказания для {len(predictions)} SKU")
            return predictions
            
        except Exception as e:
            logger.error(f"Ошибка предсказания всех SARIMA моделей: {e}")
            raise

    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает качество SARIMA моделей"""
        try:
            if not self.is_trained:
                raise ValueError("SARIMA модели не обучены")
            
            evaluation = {
                'model_type': 'sarima',
                'evaluated_at': datetime.now().isoformat(),
                'models_evaluated': len(self.models),
                'metrics': self.model_info.get('metrics', {}),
                'models_summary': self.model_info.get('models_summary', [])
            }
            
            logger.info(f"Оценка SARIMA моделей: {len(self.models)} моделей")
            return evaluation
            
        except Exception as e:
            logger.error(f"Ошибка оценки SARIMA моделей: {e}")
            raise

class EnsembleModel(BaseMLModel):
    """Ансамбль моделей для улучшения прогнозирования"""
    
    def __init__(self):
        super().__init__("ensemble")
        self.models = {
            'linear': LinearRegressionModel(),
            'random_forest': RandomForestModel(),
            'sarima': SARIMAModel()
        }
        self.weights = {
            'linear': 0.3,
            'random_forest': 0.5,
            'sarima': 0.2
        }
        self.is_trained = False
        self.model_info = {}
        
    def train(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обучает ансамбль моделей"""
        try:
            logger.info("Начало обучения ансамбля моделей")
            
            results = {}
            
            # Обучаем каждую модель
            for name, model in self.models.items():
                try:
                    if name == 'sarima':
                        model_info = model.train(sales_data)
                    else:
                        model_info = model.train(sales_data)
                    
                    results[name] = model_info
                    logger.info(f"Модель {name} обучена успешно")
                    
                except Exception as e:
                    logger.error(f"Ошибка обучения модели {name}: {e}")
                    results[name] = {'error': str(e)}
            
            # Проверяем, что хотя бы одна модель обучена
            trained_models = [name for name, result in results.items() 
                            if 'error' not in result]
            
            if not trained_models:
                raise ValueError("Ни одна модель не была обучена успешно")
            
            # Обновляем веса только для обученных моделей
            total_weight = sum(self.weights[name] for name in trained_models)
            for name in trained_models:
                self.weights[name] /= total_weight
            
            self.model_info = {
                'model_type': 'ensemble',
                'trained_at': datetime.now().isoformat(),
                'trained_models': trained_models,
                'weights': self.weights,
                'results': results
            }
            
            self.is_trained = True
            
            logger.info(f"Ансамбль обучен. Обучено моделей: {len(trained_models)}")
            return self.model_info
            
        except Exception as e:
            logger.error(f"Ошибка обучения ансамбля: {e}")
            raise
    
    def predict(self, features: List[Dict[str, Any]]) -> List[float]:
        """Делает предсказания ансамблем"""
        try:
            if not self.is_trained:
                raise ValueError("Ансамбль не обучен")
            
            predictions = {}
            
            # Получаем предсказания от каждой модели
            for name, model in self.models.items():
                if name in self.model_info['trained_models']:
                    try:
                        if name == 'sarima':
                            # Для SARIMA нужен SKU
                            if 'sku' in features[0]:
                                sku = features[0]['sku']
                                pred = model.predict(sku, steps=len(features))
                                predictions[name] = pred
                        else:
                            pred = model.predict(features)
                            predictions[name] = pred
                    except Exception as e:
                        logger.warning(f"Ошибка предсказания модели {name}: {e}")
                        continue
            
            if not predictions:
                raise ValueError("Нет предсказаний от обученных моделей")
            
            # Взвешенное среднее предсказаний
            ensemble_predictions = []
            for i in range(len(features)):
                weighted_sum = 0
                total_weight = 0
                
                for name, pred_list in predictions.items():
                    if i < len(pred_list):
                        weight = self.weights[name]
                        weighted_sum += pred_list[i] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    ensemble_predictions.append(weighted_sum / total_weight)
                else:
                    ensemble_predictions.append(0)
            
            logger.info(f"Сделано {len(ensemble_predictions)} ансамблевых предсказаний")
            return ensemble_predictions
            
        except Exception as e:
            logger.error(f"Ошибка ансамблевого предсказания: {e}")
            raise
    
    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает качество ансамбля"""
        try:
            if not self.is_trained:
                raise ValueError("Ансамбль не обучен")
            
            evaluation = {
                'model_type': 'ensemble',
                'evaluated_at': datetime.now().isoformat(),
                'trained_models': self.model_info['trained_models'],
                'weights': self.weights,
                'individual_evaluations': {}
            }
            
            # Оцениваем каждую модель отдельно
            for name in self.model_info['trained_models']:
                try:
                    model_eval = self.models[name].evaluate(test_data)
                    evaluation['individual_evaluations'][name] = model_eval
                except Exception as e:
                    logger.warning(f"Ошибка оценки модели {name}: {e}")
            
            logger.info("Ансамбль оценен")
            return evaluation
            
        except Exception as e:
            logger.error(f"Ошибка оценки ансамбля: {e}")
            raise 