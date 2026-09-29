SELECT
    COUNT(DISTINCT sp.stock_id) AS stocks_with_prices,
    COUNT(*)::numeric / COUNT(DISTINCT sp.stock_id) AS mean_prices_per_stock
FROM stock_prices sp;