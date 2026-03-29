CREATE TABLE stocks (
    stock_id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE,
    name VARCHAR(100),
    sector VARCHAR(50),
    market VARCHAR(50)
);

CREATE TABLE stock_prices (
    price_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    datetime TIMESTAMP,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC
);

CREATE TABLE technical_indicators (
    indicator_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    datetime TIMESTAMP,
    sma_5 NUMERIC,
    sma_10 NUMERIC,
    sma_20 NUMERIC,
    sma_50 NUMERIC,
    ema_12 NUMERIC,
    ema_26 NUMERIC,
    rsi NUMERIC,
    macd NUMERIC,
    macd_signal NUMERIC,
    macd_hist NUMERIC,
    stochastic_k NUMERIC,
    stochastic_d NUMERIC,
    roc NUMERIC,
    bollinger_upper NUMERIC,
    bollinger_lower NUMERIC,
    bollinger_width NUMERIC,
    atr NUMERIC,
    obv NUMERIC
);
CREATE TABLE trends (
    trend_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    keyword_id INT,
    datetime TIMESTAMP,
    trend_value NUMERIC
);
CREATE TABLE keywords (
    keyword_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    keyword VARCHAR(100),
    source VARCHAR(100),
    created_at TIMESTAMP
);
CREATE TABLE keyword_scores (
    score_id SERIAL PRIMARY KEY,
    keyword_id INT REFERENCES keywords(keyword_id),
    datetime TIMESTAMP,
    correlation_7d NUMERIC,
    correlation_30d NUMERIC,
    lag_3_corr NUMERIC,
    lag_7_corr NUMERIC,
    sentiment_score NUMERIC,
    final_score NUMERIC
);
CREATE TABLE features (
    feature_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    datetime TIMESTAMP,
    return_1d NUMERIC,
    return_7d NUMERIC,
    volatility_7d NUMERIC,
    rsi NUMERIC,
    macd NUMERIC,
    macd_hist NUMERIC,
    sma_20_diff NUMERIC,
    ema_diff NUMERIC,
    bollinger_width NUMERIC,
    atr NUMERIC,
    obv NUMERIC,

    trend_value NUMERIC,
    trend_change NUMERIC,
    trend_lag_3 NUMERIC,
    trend_lag_7 NUMERIC,

    keyword_score NUMERIC,

    target_price_up NUMERIC,
    target_return_5d NUMERIC
)
CREATE TABLE predictions (
    prediction_id SERIAL PRIMARY KEY,
    stock_id INT REFERENCES stocks(stock_id),
    datetime TIMESTAMP,
    predicted_price NUMERIC,
    predicted_return NUMERIC,
    predicted_direction NUMERIC,
    confidence NUMERIC,
    model_id INT REFERENCES models(model_id)
);
CREATE TABLE models (
    model_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    version VARCHAR(50),
    algorithm VARCHAR(100),
    features_used TEXT,
    created_at TIMESTAMP,
    accuracy NUMERIC,
    mse NUMERIC,
    mae NUMERIC
)
