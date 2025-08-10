from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import numpy as np

app = FastAPI(title="Stub ML Service", version="0.1.0")


class TrainRequest(BaseModel):
    sales_data: List[Dict[str, Any]]


class PredictRequest(BaseModel):
    features: List[Dict[str, Any]]
    sku: Optional[str] = None
    steps: int = 30


@app.get("/models/status")
async def status() -> Dict[str, Any]:
    return {
        "status": {
            "linear_regression": {"trained": True},
            "random_forest": {"trained": True},
            "sarima": {"trained": False},
            "ensemble": {"trained": True},
        }
    }


@app.post("/models/train")
async def train(req: TrainRequest) -> Dict[str, Any]:
    # Заглушка обучения
    return {"ok": True, "samples": len(req.sales_data)}


@app.post("/models/predict")
async def predict(req: PredictRequest) -> Dict[str, Any]:
    n = len(req.features)
    # Простейшие предсказания: небольшое положительное число, чтобы не давать нулевые продажи
    # Имитируем ансамбль и линейную регрессию
    base = np.full(n, 1.0, dtype=float)
    return {
        "predictions": {
            "ensemble": base.tolist(),
            "linear_regression": (base * 0.9).tolist(),
        }
    }
