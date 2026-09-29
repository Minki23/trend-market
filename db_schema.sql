-- Normalized schema for stock data imported from yfinance JSON
-- PostgreSQL-specific DDL

CREATE TABLE sectors (
    sector_id BIGSERIAL PRIMARY KEY,
    sector_key VARCHAR(100) NOT NULL UNIQUE,
    sector_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE industries (
    industry_id BIGSERIAL PRIMARY KEY,
    sector_id BIGINT NOT NULL REFERENCES sectors(sector_id) ON DELETE RESTRICT,
    industry_key VARCHAR(100) NOT NULL UNIQUE,
    industry_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE addresses (
    address_id BIGSERIAL PRIMARY KEY,
    address_line_1 VARCHAR(255),
    city VARCHAR(100),
    zip_code VARCHAR(50),
    country VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stocks (
    stock_id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    short_name VARCHAR(255),
    long_name VARCHAR(255),
    exchange VARCHAR(50),
    market VARCHAR(100),
    address_id BIGINT REFERENCES addresses(address_id) ON DELETE SET NULL,
    sector_id BIGINT REFERENCES sectors(sector_id) ON DELETE SET NULL,
    industry_id BIGINT REFERENCES industries(industry_id) ON DELETE SET NULL,
    website VARCHAR(500),
    long_business_summary TEXT,
    full_time_employees INTEGER,
    currency VARCHAR(10),
    quote_type VARCHAR(50),
    market_state VARCHAR(50),
    language VARCHAR(20),
    region VARCHAR(50),
    type_disp VARCHAR(50),
    tradeable BOOLEAN,
    triggerable BOOLEAN,
    has_pre_post_market_data BOOLEAN,
    source_interval INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_officers (
    officer_id BIGSERIAL PRIMARY KEY,
    stock_id BIGINT NOT NULL REFERENCES stocks(stock_id) ON DELETE CASCADE,
    officer_name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    fiscal_year INTEGER,
    total_pay NUMERIC(14,2),
    exercised_value NUMERIC(14,2),
    unexercised_value NUMERIC(14,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (stock_id, officer_name, title)
);

CREATE TABLE stock_quote_snapshots (
    quote_id BIGSERIAL PRIMARY KEY,
    stock_id BIGINT NOT NULL REFERENCES stocks(stock_id) ON DELETE CASCADE,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    previous_close NUMERIC(12,4),
    regular_market_previous_close NUMERIC(12,4),
    open_price NUMERIC(12,4),
    regular_market_open NUMERIC(12,4),
    day_low NUMERIC(12,4),
    regular_market_day_low NUMERIC(12,4),
    day_high NUMERIC(12,4),
    regular_market_day_high NUMERIC(12,4),
    volume BIGINT,
    regular_market_volume BIGINT,
    average_volume BIGINT,
    average_volume_10_days BIGINT,
    average_daily_volume_10_day BIGINT,
    bid NUMERIC(12,4),
    ask NUMERIC(12,4),
    market_cap BIGINT,
    enterprise_value BIGINT,
    non_diluted_market_cap BIGINT,
    fifty_two_week_low NUMERIC(12,4),
    fifty_two_week_high NUMERIC(12,4),
    all_time_high NUMERIC(12,4),
    all_time_low NUMERIC(12,4),
    price_to_sales_trailing_12_months NUMERIC(12,4),
    fifty_day_average NUMERIC(12,4),
    two_hundred_day_average NUMERIC(12,4),
    beta NUMERIC(10,4),
    trailing_pe NUMERIC(12,4),
    forward_pe NUMERIC(12,4),
    book_value NUMERIC(12,4),
    price_to_book NUMERIC(12,4),
    dividend_rate NUMERIC(12,4),
    dividend_yield NUMERIC(12,4),
    payout_ratio NUMERIC(12,4),
    trailing_annual_dividend_rate NUMERIC(12,4),
    trailing_annual_dividend_yield NUMERIC(12,4),
    last_dividend_value NUMERIC(12,4),
    profit_margins NUMERIC(12,4),
    return_on_assets NUMERIC(12,4),
    return_on_equity NUMERIC(12,4),
    gross_profits BIGINT,
    free_cashflow BIGINT,
    operating_cashflow BIGINT,
    total_cash BIGINT,
    total_debt BIGINT,
    quick_ratio NUMERIC(12,4),
    current_ratio NUMERIC(12,4),
    total_revenue BIGINT,
    revenue_per_share NUMERIC(12,4),
    earnings_growth NUMERIC(12,4),
    revenue_growth NUMERIC(12,4),
    gross_margins NUMERIC(12,4),
    ebitda_margins NUMERIC(12,4),
    operating_margins NUMERIC(12,4),
    fifty_two_week_change_percent NUMERIC(12,4),
    regular_market_change_percent NUMERIC(12,4),
    regular_market_change NUMERIC(12,4),
    trailing_peg_ratio NUMERIC(12,4),
    current_price NUMERIC(12,4),
    regular_market_price NUMERIC(12,4),
    UNIQUE (stock_id, snapshot_at)
);

CREATE INDEX idx_stocks_ticker ON stocks (ticker);
CREATE INDEX idx_stocks_sector_id ON stocks (sector_id);
CREATE INDEX idx_stocks_industry_id ON stocks (industry_id);
CREATE INDEX idx_stock_quotes_stock_id ON stock_quote_snapshots (stock_id, snapshot_at);
CREATE INDEX idx_stock_officers_stock_id ON stock_officers (stock_id);
