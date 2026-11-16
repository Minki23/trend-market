from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.prediction.predictor import StockPredictor

app = FastAPI(title="Stock Prediction ML Service", version="1.0.0")


class PredictRequest(BaseModel):
    stock_id: int
    model_key: Optional[str] = None


class PredictResponse(BaseModel):
    stock_id: int
    horizon: int
    predicted_return: float
    predicted_direction: str


@app.post("/api/predict", response_model=PredictResponse)
def predict_stock(req: PredictRequest) -> PredictResponse:
    """Predict future return for a single stock_id (Point 45)."""
    try:
        predictor = StockPredictor(model_key=req.model_key)
        res = predictor.predict_for_stock(stock_id=req.stock_id)
        return PredictResponse(
            stock_id=res["stock_id"],
            horizon=res["horizon"],
            predicted_return=res["predicted_return"],
            predicted_direction=res["predicted_direction"],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
