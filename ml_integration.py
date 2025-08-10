"""
Интеграция ML-моделей с основным прогнозированием (remote-only)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import numpy as np
import pandas as pd
import requests

from config import logger


class MLForecastIntegration:
    """Интеграция с удалённым ML-сервисом без локальных фоллбэков"""

    def __init__(self, ml_service_url: Optional[str] = None) -> None:
        # По умолчанию используем IPv4 loopback, чтобы избежать проблем c IPv6 (::1)
        default_url = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8006")
        self.ml_service_url = ml_service_url or default_url
        self.logger = logger

    def prepare_ml_features(self, sales_df: pd.DataFrame, forecast_days: int = 30) -> List[Dict[str, Any]]:
        """Готовит признаки для будущих дат по всем SKU"""
        try:
            if sales_df.empty:
                return []

            if 'date' not in sales_df.columns:
                return []

            # Приводим дату к datetime и отбрасываем некорректные
            sales_df = sales_df.copy()
            sales_df['date'] = pd.to_datetime(sales_df['date'], errors='coerce')
            sales_df = sales_df.dropna(subset=['date'])
            if sales_df.empty:
                return []

            last_date = sales_df['date'].max()
            if pd.isna(last_date):
                return []

            future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=forecast_days, freq='D')

            features: List[Dict[str, Any]] = []
            unique_skus = sales_df['sku'].unique().tolist() if 'sku' in sales_df.columns else [None]

            for date in future_dates:
                base = {
                    'date': date.isoformat(),
                    'day_of_week': int(date.dayofweek),
                    'month': int(date.month),
                    'day_of_month': int(date.day),
                    'is_weekend': 1 if date.dayofweek in [5, 6] else 0,
                    'is_month_start': 1 if date.is_month_start else 0,
                    'is_month_end': 1 if date.is_month_end else 0,
                    'quarter': int(date.quarter),
                    'week_of_year': int(date.isocalendar().week),
                }
                for sku in unique_skus:
                    row = dict(base)
                    if sku is not None:
                        row['sku'] = str(sku)
                    features.append(row)

            self.logger.info(f"Подготовлено {len(features)} признаков для ML")
            return features
        except Exception as exc:
            self.logger.error(f"Ошибка подготовки признаков для ML: {exc}")
            return []

    def train_ml_models(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Отправляет данные на обучение в удалённый сервис"""
        try:
            resp = requests.post(f"{self.ml_service_url}/models/train", json={'sales_data': sales_data}, timeout=300)
            return resp.json() if resp.status_code == 200 else {'error': resp.text}
        except Exception as exc:
            return {'error': str(exc)}

    def get_ml_predictions(self, features: List[Dict[str, Any]], sku: Optional[str] = None, steps: int = 30) -> Dict[str, Any]:
        """Запрашивает предсказания у удалённого сервиса"""
        try:
            payload = {'features': features, 'sku': sku, 'steps': steps}
            resp = requests.post(f"{self.ml_service_url}/models/predict", json=payload, timeout=60)
            return resp.json() if resp.status_code == 200 else {'error': resp.text}
        except Exception as exc:
            return {'error': str(exc)}

    def get_ml_model_status(self) -> Dict[str, Any]:
        """Статус обученности/готовности моделей на удалённом сервисе"""
        try:
            resp = requests.get(f"{self.ml_service_url}/models/status", timeout=10)
            return resp.json() if resp.status_code == 200 else {'error': resp.text}
        except Exception as exc:
            return {'error': str(exc)}

    def enhance_forecast_with_ml(self, forecast_df: pd.DataFrame, sales_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Улучшает среднюю дневную продажу по SKU на основе предсказаний удалённого сервиса"""
        if forecast_df.empty:
            return forecast_df

        features = self.prepare_ml_features(pd.DataFrame(sales_data), forecast_days=30)
        if not features:
            self.logger.warning("Не удалось подготовить признаки для удалённого ML")
            return forecast_df

        predictions = self.get_ml_predictions(features)
        if 'error' in predictions:
            self.logger.warning(f"Удалённый ML недоступен: {predictions['error']}")
            return forecast_df

        enhanced = forecast_df.copy()
        preds = predictions.get('predictions', {})

        # Поддержка ансамбля
        if isinstance(preds, dict) and 'ensemble' in preds and isinstance(preds['ensemble'], list):
            ensemble_pred = preds['ensemble']
            for i, row in enhanced.iterrows():
                sku = row['sku']
                sku_preds = [ensemble_pred[j] for j, f in enumerate(features) if f.get('sku') == sku and j < len(ensemble_pred)]
                if sku_preds:
                    ml_avg = float(np.mean(sku_preds))
                    original_avg = float(row['avg_daily_sales'])
                    enhanced.loc[i, 'avg_daily_sales'] = 0.7 * ml_avg + 0.3 * original_avg
                    enhanced.loc[i, 'forecast_quality'] = 'ML_ENHANCED'
        # Линейная регрессия
        elif isinstance(preds, dict) and 'linear_regression' in preds and isinstance(preds['linear_regression'], list):
            linear_pred = preds['linear_regression']
            for i, row in enhanced.iterrows():
                sku = row['sku']
                sku_preds = [linear_pred[j] for j, f in enumerate(features) if f.get('sku') == sku and j < len(linear_pred)]
                if sku_preds:
                    ml_avg = float(np.mean(sku_preds))
                    original_avg = float(row['avg_daily_sales'])
                    enhanced.loc[i, 'avg_daily_sales'] = 0.6 * ml_avg + 0.4 * original_avg
                    enhanced.loc[i, 'forecast_quality'] = 'ML_ENHANCED'
        else:
            self.logger.info("Получен неожиданный формат предсказаний, прогноз не изменён")

        # Пересчёт производных метрик
        from config import DAYS_FORECAST_SHORT, DAYS_FORECAST_LONG, get_moq_for_sku
        enhanced['days_until_stockout'] = np.where(
            enhanced['avg_daily_sales'] > 0,
            enhanced['available_stock'] / enhanced['avg_daily_sales'],
            float('inf'),
        )
        enhanced['needs_purchase_short'] = enhanced['days_until_stockout'] < DAYS_FORECAST_SHORT
        enhanced['needs_purchase_long'] = enhanced['days_until_stockout'] < DAYS_FORECAST_LONG
        enhanced['recommended_quantity'] = np.where(
            enhanced['needs_purchase_short'],
            np.maximum(
                (DAYS_FORECAST_LONG - enhanced['days_until_stockout']) * enhanced['avg_daily_sales'],
                enhanced['avg_daily_sales'] * DAYS_FORECAST_SHORT,
            ),
            0,
        )
        enhanced['moq'] = enhanced['sku'].apply(get_moq_for_sku)
        enhanced['final_order_quantity'] = np.where(
            enhanced['recommended_quantity'] > 0,
            np.maximum(enhanced['recommended_quantity'], enhanced['moq']),
            0,
        ).round().astype(int)

        self.logger.info(f"Прогноз улучшен с помощью удалённого ML для {len(enhanced)} SKU")
        return enhanced

    def compare_forecast_methods(self, sales_data: List[Dict[str, Any]], stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Сравнивает базовый и ML-улучшенный прогнозы"""
        from forecast import PurchaseForecast

        pf = PurchaseForecast()
        sales_df = pf.prepare_sales_data(sales_data)
        stocks_df = pf.prepare_stocks_data(stocks_data)
        base = pf.calculate_forecast(sales_df, stocks_df)
        ml = self.enhance_forecast_with_ml(base, sales_data)

        comparison = {
            'base_forecast': {
                'total_skus': int(len(base)),
                'skus_needing_purchase': int(len(base[base['needs_purchase_short']])) if not base.empty else 0,
                'total_quantity': int(base['final_order_quantity'].sum()) if not base.empty else 0,
                'avg_days_until_stockout': float(base['days_until_stockout'].mean()) if not base.empty else 0.0,
            },
            'ml_enhanced_forecast': {
                'total_skus': int(len(ml)),
                'skus_needing_purchase': int(len(ml[ml['needs_purchase_short']])) if not ml.empty else 0,
                'total_quantity': int(ml['final_order_quantity'].sum()) if not ml.empty else 0,
                'avg_days_until_stockout': float(ml['days_until_stockout'].mean()) if not ml.empty else 0.0,
            },
        }
        improvements = {
            'quantity_difference': comparison['ml_enhanced_forecast']['total_quantity'] - comparison['base_forecast']['total_quantity'],
            'purchase_items_difference': comparison['ml_enhanced_forecast']['skus_needing_purchase'] - comparison['base_forecast']['skus_needing_purchase'],
        }
        comparison['improvements'] = improvements
        return comparison

    def generate_ml_forecast_report(self, sales_data: List[Dict[str, Any]], stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Формирует полный ML-отчёт и сохраняет его в файл"""
        status = self.get_ml_model_status()
        comparison = self.compare_forecast_methods(sales_data, stocks_data)

        report = {
            'timestamp': datetime.now().isoformat(),
            'ml_service_url': self.ml_service_url,
            'ml_models_status': status,
            'forecast_comparison': comparison,
            'notes': [],
        }
        if isinstance(status, dict) and 'error' in status:
            report['notes'].append({'type': 'WARNING', 'message': f"ML service error: {status['error']}"})

        reports_dir = Path('reports')
        reports_dir.mkdir(exist_ok=True)
        filepath = reports_dir / f"ml_forecast_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.logger.info(f"ML-отчёт сохранён: {filepath}")
        return {'filepath': str(filepath), 'report': report}
