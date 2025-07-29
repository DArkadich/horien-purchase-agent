"""
Модуль для расчета оборачиваемости и потребности в закупках
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from config import (
    DAYS_FORECAST_SHORT, DAYS_FORECAST_LONG, SALES_HISTORY_DAYS,
    get_moq_for_sku, logger
)

class PurchaseForecast:
    """Класс для расчета прогнозов закупок"""
    
    def __init__(self):
        self.days_forecast_short = DAYS_FORECAST_SHORT
        self.days_forecast_long = DAYS_FORECAST_LONG
        self.sales_history_days = SALES_HISTORY_DAYS
    
    def prepare_sales_data(self, sales_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Подготавливает данные о продажах для анализа
        """
        logger.info("Подготовка данных о продажах...")
        
        # Преобразуем в DataFrame
        df = pd.DataFrame(sales_data)
        
        if df.empty:
            logger.warning("Нет данных о продажах")
            return pd.DataFrame()
        
        # Обрабатываем даты
        df['date'] = pd.to_datetime(df['date'])
        
        # Группируем по SKU и дате
        sales_by_sku = df.groupby(['sku', 'date']).agg({
            'quantity': 'sum',
            'revenue': 'sum'
        }).reset_index()
        
        logger.info(f"Подготовлено {len(sales_by_sku)} записей о продажах")
        return sales_by_sku
    
    def prepare_stocks_data(self, stocks_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Подготавливает данные об остатках
        """
        logger.info("Подготовка данных об остатках...")
        
        # Преобразуем в DataFrame
        df = pd.DataFrame(stocks_data)
        
        if df.empty:
            logger.warning("Нет данных об остатках")
            return pd.DataFrame()
        
        # Группируем по SKU
        stocks_by_sku = df.groupby('sku').agg({
            'stock': 'sum',
            'reserved': 'sum'
        }).reset_index()
        
        # Рассчитываем доступный остаток
        stocks_by_sku['available_stock'] = stocks_by_sku['stock'] - stocks_by_sku['reserved']
        
        logger.info(f"Подготовлено {len(stocks_by_sku)} записей об остатках")
        return stocks_by_sku
    
    def calculate_daily_sales(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Рассчитывает среднюю дневную продажу для каждого SKU, исключая дни OOS
        """
        logger.info("Расчет средней дневной продажи (исключая дни OOS)...")
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Если есть данные об остатках, используем их для точного определения OOS
        if stocks_df is not None and not stocks_df.empty:
            # Объединяем продажи с остатками по SKU
            sales_with_stocks = sales_df.merge(stocks_df[['sku', 'available_stock']], on='sku', how='left')
            
            # Определяем дни OOS: когда остаток = 0 или отсутствует
            sales_with_stocks['is_oos'] = (sales_with_stocks['available_stock'].isna() | 
                                         (sales_with_stocks['available_stock'] == 0))
            
            # Фильтруем только дни когда товар был в наличии (исключаем дни OOS)
            # Включаем все дни с наличием товара, даже если продаж не было
            days_with_stock = sales_with_stocks[~sales_with_stocks['is_oos']].copy()
            
            logger.info(f"Используем данные об остатках для определения OOS дней")
        else:
            # Если нет данных об остатках, используем старую логику
            days_with_stock = sales_df.copy()
            logger.info(f"Данные об остатках недоступны, используем все дни")
        
        if days_with_stock.empty:
            logger.warning("Нет данных о днях с наличием товара")
            return pd.DataFrame()
        
        # Группируем по SKU и рассчитываем среднюю дневную продажу за дни с наличием товара
        daily_sales = days_with_stock.groupby('sku').agg({
            'quantity': 'sum',
            'date': 'nunique'
        }).reset_index()
        
        daily_sales['avg_daily_sales'] = daily_sales['quantity'] / daily_sales['date']
        daily_sales['total_sales_days'] = daily_sales['date']
        
        # Убираем колонку с количеством уникальных дат
        daily_sales = daily_sales.drop('date', axis=1)
        
        logger.info(f"Рассчитана средняя дневная продажа для {len(daily_sales)} SKU (за дни с наличием товара)")
        
        # Логируем примеры для отладки
        for _, row in daily_sales.head(3).iterrows():
            logger.info(f"SKU {row['sku']}: {row['avg_daily_sales']:.2f} шт/день за {row['total_sales_days']} дней с наличием товара")
        
        return daily_sales
    
    def identify_oos_days(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Идентифицирует дни, когда товары были в OOS (out of stock) для информационных целей
        """
        logger.info("Идентификация дней OOS для анализа...")
        
        if sales_df.empty or stocks_df.empty:
            return pd.DataFrame()
        
        # Создаем полный диапазон дат для каждого SKU
        date_range = pd.date_range(
            start=sales_df['date'].min(),
            end=sales_df['date'].max(),
            freq='D'
        )
        
        # Создаем все комбинации SKU и дат
        all_combinations = []
        for sku in sales_df['sku'].unique():
            for date in date_range:
                all_combinations.append({'sku': sku, 'date': date})
        
        combinations_df = pd.DataFrame(all_combinations)
        
        # Объединяем с реальными продажами
        merged_df = combinations_df.merge(
            sales_df, on=['sku', 'date'], how='left'
        ).fillna(0)
        
        # Определяем дни OOS (когда продажи = 0)
        merged_df['is_oos'] = merged_df['quantity'] == 0
        
        # Подсчитываем статистику OOS для каждого SKU
        oos_stats = merged_df.groupby('sku').agg({
            'is_oos': 'sum',
            'date': 'count'
        }).reset_index()
        
        oos_stats['oos_percentage'] = (oos_stats['is_oos'] / oos_stats['date'] * 100).round(1)
        
        # Логируем статистику OOS
        for _, row in oos_stats.head(5).iterrows():
            logger.info(f"SKU {row['sku']}: {row['oos_percentage']}% дней OOS ({row['is_oos']} из {row['date']} дней)")
        
        logger.info(f"Идентифицировано {merged_df['is_oos'].sum()} дней OOS из {len(merged_df)} общих дней")
        return merged_df
    
    def calculate_forecast(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Рассчитывает прогноз закупок для каждого SKU
        """
        logger.info("Расчет прогноза закупок...")
        
        if sales_df.empty or stocks_df.empty:
            return pd.DataFrame()
        
        # Рассчитываем среднюю дневную продажу
        daily_sales = self.calculate_daily_sales(sales_df, stocks_df)
        
        # Объединяем с остатками
        forecast_df = daily_sales.merge(stocks_df, on='sku', how='left')
        
        # Рассчитываем, на сколько дней хватит текущего запаса
        forecast_df['days_until_stockout'] = np.where(
            forecast_df['avg_daily_sales'] > 0,
            forecast_df['available_stock'] / forecast_df['avg_daily_sales'],
            float('inf')
        )
        
        # Определяем необходимость закупки
        forecast_df['needs_purchase_short'] = forecast_df['days_until_stockout'] < self.days_forecast_short
        forecast_df['needs_purchase_long'] = forecast_df['days_until_stockout'] < self.days_forecast_long
        
        # Рассчитываем рекомендуемое количество для закупки
        forecast_df['recommended_quantity'] = np.where(
            forecast_df['needs_purchase_short'],
            np.maximum(
                (self.days_forecast_long - forecast_df['days_until_stockout']) * forecast_df['avg_daily_sales'],
                forecast_df['avg_daily_sales'] * self.days_forecast_short
            ),
            0
        )
        
        # Применяем минимальные партии
        forecast_df['moq'] = forecast_df['sku'].apply(get_moq_for_sku)
        forecast_df['final_order_quantity'] = np.where(
            forecast_df['recommended_quantity'] > 0,
            np.maximum(forecast_df['recommended_quantity'], forecast_df['moq']),
            0
        )
        
        # Округляем до целых чисел
        forecast_df['final_order_quantity'] = forecast_df['final_order_quantity'].round().astype(int)
        
        logger.info(f"Рассчитан прогноз для {len(forecast_df)} SKU")
        return forecast_df
    
    def generate_purchase_report(self, forecast_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Генерирует отчет о закупках
        """
        logger.info("Генерация отчета о закупках...")
        
        if forecast_df.empty:
            return []
        
        # Фильтруем SKU, которые требуют закупки
        purchase_items = forecast_df[forecast_df['needs_purchase_short']].copy()
        
        if purchase_items.empty:
            logger.info("Нет товаров, требующих закупки")
            return []
        
        # Сортируем по приоритету (по убыванию срочности)
        purchase_items = purchase_items.sort_values('days_until_stockout', ascending=True)
        
        # Формируем отчет
        report = []
        for _, row in purchase_items.iterrows():
            report_item = {
                'sku': row['sku'],
                'avg_daily_sales': round(row['avg_daily_sales'], 2),
                'current_stock': int(row['available_stock']),
                'days_until_stockout': round(row['days_until_stockout'], 1),
                'recommended_quantity': int(row['final_order_quantity']),
                'moq': int(row['moq']),
                'urgency': 'HIGH' if row['days_until_stockout'] < 10 else 'MEDIUM' if row['days_until_stockout'] < 20 else 'LOW'
            }
            report.append(report_item)
        
        logger.info(f"Сгенерирован отчет для {len(report)} SKU")
        return report
    
    def generate_telegram_message(self, report: List[Dict[str, Any]]) -> str:
        """
        Генерирует сообщение для Telegram
        """
        if not report:
            return "Нет товаров, требующих закупки."
        
        message = "🛒 *Отчет о закупках*\n\n"
        
        for item in report[:10]:  # Ограничиваем первыми 10 позициями
            sku = item['sku']
            days_left = item['days_until_stockout']
            quantity = item['recommended_quantity']
            
            urgency_emoji = "🔴" if item['urgency'] == 'HIGH' else "🟡" if item['urgency'] == 'MEDIUM' else "🟢"
            
            message += f"{urgency_emoji} {sku} → хватит на {days_left} дней. Заказать {quantity} шт\n"
        
        if len(report) > 10:
            message += f"\n... и еще {len(report) - 10} позиций"
        
        message += f"\n\nВсего позиций для закупки: {len(report)}"
        
        return message 