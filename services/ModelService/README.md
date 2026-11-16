# Stock Prediction ML Pipeline

End-to-end Machine Learning pipeline for predicting 7-session forward stock returns (`target_7d`) from historical OHLCV prices and technical indicators stored in PostgreSQL.

## Architecture

```text
PostgreSQL (technical_indicators + stock_prices)
    -> DataLoader (chunked by stock batches / date ranges)
    -> DataValidator ((stock_id, datetime) uniqueness, range & history checks, chronological sorting)
    -> Feature Engineering (returns, volatility, EMA distances, Bollinger position, volume, RSI, MACD, OBV)
    -> Lag Features (1, 2, 3, 5, 10, 20 sessions per stock_id)
    -> Target Generation (target_7d = close[t+7] / close[t] - 1, configurable horizon)
    -> Chronological Split & Parquet Persistence (data/processed/{train,validation,test}.parquet)
    -> Walk-Forward Validation & Hyperparameter Tuning (ZeroBaseline, LinearRegression, Ridge, ElasticNet, XGBoost, LightGBM)
    -> Multi-Criteria Model Selection & Persistence (models/<model>/model.joblib + metadata.json)
    -> Prediction, Multi-Stock Ranking & FastAPI Service (POST /api/predict)
```

## Setup

1. Copy `.env.example` to `.env` and configure PostgreSQL credentials:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=stocks
   DB_USER=admin
   DB_PASSWORD=admin
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Train & Validate Models
```bash
python main.py train --max-stocks 100 --horizon 7 --lookback 20 --training-years 3
```

### 2. Predict for a Single Stock
```bash
python main.py predict --stock-id 1
```

### 3. Predict & Rank Multiple Stocks
```bash
python main.py rank --max-stocks 50 --top 15
```

### 4. Run Automated Experiment Grid
```bash
python main.py experiments --max-stocks 30
```

### 5. Start FastAPI REST Server
```bash
python main.py serve --port 8000
```
Endpoint: `POST /api/predict` with body `{"stock_id": 1}`.

### 6. Run Unit Tests
```bash
pytest -v
```

## Disclaimer

This system is intended strictly for research into the predictive power of historical market data. Historical performance does not guarantee future returns.
