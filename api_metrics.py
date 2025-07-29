#!/usr/bin/env python3
"""
Система метрик производительности API
"""

import time
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics
from config import logger, API_METRICS_DB_PATH, API_METRICS_RETENTION_DAYS, API_METRICS_ALERT_THRESHOLDS

class MetricType(Enum):
    """Типы метрик"""
    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CACHE_HIT_RATE = "cache_hit_rate"
    RETRY_COUNT = "retry_count"

@dataclass
class APIMetric:
    """Метрика API"""
    timestamp: datetime
    endpoint: str
    metric_type: MetricType
    value: float
    metadata: Dict[str, Any]

class APIMetricsCollector:
    """Сборщик метрик производительности API"""
    
    def __init__(self, db_path: str = API_METRICS_DB_PATH):
        self.db_path = db_path
        self._init_db()
        
        # Кэш для временных метрик
        self.metrics_cache = {}
        
        # Настройки агрегации
        self.aggregation_intervals = [1, 5, 15, 60]  # минуты
        self.retention_days = API_METRICS_RETENTION_DAYS
    
    def _init_db(self):
        """Инициализация базы данных для метрик"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для сырых метрик
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                endpoint TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                metadata TEXT
            )
        ''')
        
        # Создаем индексы отдельно
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON api_metrics(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_endpoint ON api_metrics(endpoint)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_type ON api_metrics(metric_type)')
        
        # Таблица для агрегированных метрик
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_metrics_aggregated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                interval_minutes INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                avg_value REAL,
                min_value REAL,
                max_value REAL,
                count INTEGER
            )
        ''')
        
        # Создаем индексы для агрегированных метрик
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agg_timestamp ON api_metrics_aggregated(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agg_endpoint ON api_metrics_aggregated(endpoint)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agg_type ON api_metrics_aggregated(metric_type)')
        
        # Таблица для алертов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alert_type TEXT NOT NULL,
                endpoint TEXT,
                message TEXT,
                severity TEXT,
                resolved BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Создаем индексы для алертов
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON api_alerts(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_type ON api_alerts(alert_type)')
        
        conn.commit()
        conn.close()
        logger.info("База данных метрик API инициализирована")
    
    def record_metric(self, endpoint: str, metric_type: MetricType, value: float, 
                     metadata: Dict[str, Any] = None):
        """
        Записывает метрику
        
        Args:
            endpoint: Эндпоинт API
            metric_type: Тип метрики
            value: Значение метрики
            metadata: Дополнительные данные
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_metrics (timestamp, endpoint, metric_type, value, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                endpoint,
                metric_type.value,
                value,
                json.dumps(metadata) if metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Ошибка при записи метрики: {e}")
    
    def record_response_time(self, endpoint: str, response_time: float, 
                           status_code: int = None, error: str = None):
        """Записывает метрику времени ответа"""
        metadata = {
            'status_code': status_code,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
        
        self.record_metric(endpoint, MetricType.RESPONSE_TIME, response_time, metadata)
        
        # Проверяем алерты
        if response_time > API_METRICS_ALERT_THRESHOLDS['response_time_ms']:
            self._create_alert("high_response_time", endpoint, 
                             f"Высокое время ответа: {response_time:.0f}мс")
    
    def record_success_rate(self, endpoint: str, success_count: int, total_count: int):
        """Записывает метрику успешности"""
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        metadata = {
            'success_count': success_count,
            'total_count': total_count
        }
        
        self.record_metric(endpoint, MetricType.SUCCESS_RATE, success_rate, metadata)
        
        # Проверяем алерты
        if success_rate < API_METRICS_ALERT_THRESHOLDS['success_rate_percent']:
            self._create_alert("low_success_rate", endpoint, 
                             f"Низкая успешность: {success_rate:.1f}%")
    
    def record_error_rate(self, endpoint: str, error_count: int, total_count: int):
        """Записывает метрику ошибок"""
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        metadata = {
            'error_count': error_count,
            'total_count': total_count
        }
        
        self.record_metric(endpoint, MetricType.ERROR_RATE, error_rate, metadata)
        
        # Проверяем алерты
        if error_rate > API_METRICS_ALERT_THRESHOLDS['error_rate_percent']:
            self._create_alert("high_error_rate", endpoint, 
                             f"Высокая частота ошибок: {error_rate:.1f}%")
    
    def record_throughput(self, endpoint: str, requests_per_minute: float):
        """Записывает метрику пропускной способности"""
        metadata = {
            'requests_per_minute': requests_per_minute
        }
        
        self.record_metric(endpoint, MetricType.THROUGHPUT, requests_per_minute, metadata)
    
    def record_cache_hit_rate(self, endpoint: str, hit_rate: float):
        """Записывает метрику кэша"""
        metadata = {
            'hit_rate': hit_rate
        }
        
        self.record_metric(endpoint, MetricType.CACHE_HIT_RATE, hit_rate, metadata)
    
    def record_retry_count(self, endpoint: str, retry_count: int):
        """Записывает метрику повторных попыток"""
        metadata = {
            'retry_count': retry_count
        }
        
        self.record_metric(endpoint, MetricType.RETRY_COUNT, retry_count, metadata)
        
        # Проверяем алерты
        if retry_count > 3:
            self._create_alert("high_retry_count", endpoint, 
                             f"Много повторных попыток: {retry_count}")
    
    def _create_alert(self, alert_type: str, endpoint: str, message: str):
        """Создает алерт"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_alerts (timestamp, alert_type, endpoint, message, severity)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                alert_type,
                endpoint,
                message,
                'high' if alert_type in ['high_error_rate', 'high_response_time'] else 'medium'
            ))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"Алерт создан: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Ошибка при создании алерта: {e}")
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Получает сводку метрик за последние N часов
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Словарь со сводкой метрик
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            # Общая статистика по эндпоинтам
            cursor.execute('''
                SELECT 
                    endpoint,
                    metric_type,
                    AVG(value) as avg_value,
                    MIN(value) as min_value,
                    MAX(value) as max_value,
                    COUNT(*) as count
                FROM api_metrics 
                WHERE timestamp >= ?
                GROUP BY endpoint, metric_type
            ''', (start_time,))
            
            metrics_summary = {}
            for row in cursor.fetchall():
                endpoint, metric_type, avg_value, min_value, max_value, count = row
                
                if endpoint not in metrics_summary:
                    metrics_summary[endpoint] = {}
                
                metrics_summary[endpoint][metric_type] = {
                    'avg': avg_value or 0,
                    'min': min_value or 0,
                    'max': max_value or 0,
                    'count': count
                }
            
            # Статистика алертов
            cursor.execute('''
                SELECT 
                    alert_type,
                    COUNT(*) as count,
                    COUNT(CASE WHEN resolved = FALSE THEN 1 END) as unresolved
                FROM api_alerts 
                WHERE timestamp >= ?
                GROUP BY alert_type
            ''', (start_time,))
            
            alerts_summary = {}
            for row in cursor.fetchall():
                alert_type, count, unresolved = row
                alerts_summary[alert_type] = {
                    'total': count,
                    'unresolved': unresolved
                }
            
            conn.close()
            
            return {
                'period_hours': hours,
                'metrics': metrics_summary,
                'alerts': alerts_summary
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводки метрик: {e}")
            return {}
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """
        Получает тренды производительности
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Словарь с трендами
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            # Тренды времени ответа по часам
            cursor.execute('''
                SELECT 
                    strftime('%H', timestamp) as hour,
                    endpoint,
                    AVG(value) as avg_response_time
                FROM api_metrics 
                WHERE timestamp >= ? AND metric_type = 'response_time'
                GROUP BY hour, endpoint
                ORDER BY hour
            ''', (start_time,))
            
            response_time_trends = {}
            for row in cursor.fetchall():
                hour, endpoint, avg_response_time = row
                if endpoint not in response_time_trends:
                    response_time_trends[endpoint] = {}
                response_time_trends[endpoint][hour] = avg_response_time or 0
            
            # Тренды успешности
            cursor.execute('''
                SELECT 
                    strftime('%H', timestamp) as hour,
                    endpoint,
                    AVG(value) as avg_success_rate
                FROM api_metrics 
                WHERE timestamp >= ? AND metric_type = 'success_rate'
                GROUP BY hour, endpoint
                ORDER BY hour
            ''', (start_time,))
            
            success_rate_trends = {}
            for row in cursor.fetchall():
                hour, endpoint, avg_success_rate = row
                if endpoint not in success_rate_trends:
                    success_rate_trends[endpoint] = {}
                success_rate_trends[endpoint][hour] = avg_success_rate or 0
            
            conn.close()
            
            return {
                'response_time_trends': response_time_trends,
                'success_rate_trends': success_rate_trends
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении трендов: {e}")
            return {}
    
    def generate_performance_report(self, hours: int = 24) -> str:
        """
        Генерирует отчет о производительности
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Текстовый отчет
        """
        summary = self.get_metrics_summary(hours)
        trends = self.get_performance_trends(hours)
        
        if not summary:
            return "Нет данных для анализа"
        
        report = f"📊 *Отчет о производительности API за {hours}ч*\n\n"
        
        # Общая статистика по эндпоинтам
        for endpoint, metrics in summary.get('metrics', {}).items():
            report += f"🔗 *{endpoint}:*\n"
            
            if 'response_time' in metrics:
                rt = metrics['response_time']
                report += f"  ⏱️ Время ответа: {rt['avg']:.0f}мс (мин: {rt['min']:.0f}, макс: {rt['max']:.0f})\n"
            
            if 'success_rate' in metrics:
                sr = metrics['success_rate']
                report += f"  ✅ Успешность: {sr['avg']:.1f}%\n"
            
            if 'error_rate' in metrics:
                er = metrics['error_rate']
                report += f"  ❌ Ошибки: {er['avg']:.1f}%\n"
            
            if 'throughput' in metrics:
                tp = metrics['throughput']
                report += f"  📈 Пропускная способность: {tp['avg']:.1f} запр/мин\n"
            
            if 'cache_hit_rate' in metrics:
                chr = metrics['cache_hit_rate']
                report += f"  💾 Кэш: {chr['avg']:.1f}%\n"
            
            report += "\n"
        
        # Алерты
        alerts = summary.get('alerts', {})
        if alerts:
            report += "🚨 *Алерты:*\n"
            for alert_type, alert_data in alerts.items():
                unresolved = alert_data['unresolved']
                total = alert_data['total']
                report += f"  {alert_type}: {unresolved}/{total} неразрешенных\n"
        
        # Тренды
        if trends.get('response_time_trends'):
            report += "\n📈 *Тренды времени ответа:*\n"
            for endpoint, hours_data in trends['response_time_trends'].items():
                if hours_data:
                    avg_rt = sum(hours_data.values()) / len(hours_data)
                    report += f"  {endpoint}: {avg_rt:.0f}мс (среднее)\n"
        
        return report
    
    def cleanup_old_metrics(self, days: int = 30):
        """
        Очищает старые метрики
        
        Args:
            days: Количество дней для хранения данных
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Удаляем старые метрики
            cursor.execute('DELETE FROM api_metrics WHERE timestamp < ?', (cutoff_date,))
            deleted_metrics = cursor.rowcount
            
            # Удаляем старые агрегированные метрики
            cursor.execute('DELETE FROM api_metrics_aggregated WHERE timestamp < ?', (cutoff_date,))
            deleted_aggregated = cursor.rowcount
            
            # Удаляем старые алерты
            cursor.execute('DELETE FROM api_alerts WHERE timestamp < ?', (cutoff_date,))
            deleted_alerts = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Очищено {deleted_metrics} метрик, {deleted_aggregated} агрегированных, {deleted_alerts} алертов старше {days} дней")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых метрик: {e}")

class MetricsDecorator:
    """Декоратор для автоматического сбора метрик"""
    
    def __init__(self, metrics_collector: APIMetricsCollector):
        self.metrics_collector = metrics_collector
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = func.__name__
            
            try:
                result = func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000
                
                # Записываем метрику времени ответа
                self.metrics_collector.record_response_time(endpoint, response_time, 200)
                
                return result
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                
                # Записываем метрику ошибки
                self.metrics_collector.record_response_time(endpoint, response_time, 500, str(e))
                
                raise
        
        return wrapper 