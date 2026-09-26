SELECT
    s.stock_id,
    s.ticker,
    s.long_name,
    COUNT(sp.*) AS price_count,
    MIN(sp.date_time) AS earliest_price,
    MAX(sp.date_time) AS latest_price,
    MAX(sp.date_time) - MIN(sp.date_time) AS date_span
FROM stocks s
JOIN stock_prices sp ON sp.stock_id = s.stock_id
GROUP BY s.stock_id, s.ticker, s.long_name
ORDER BY price_count DESC
LIMIT 10;