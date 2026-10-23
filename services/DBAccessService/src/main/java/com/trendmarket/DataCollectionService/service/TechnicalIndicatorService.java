package com.trendmarket.DataCollectionService.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.TechnicalIndicator;
import com.trendmarket.DataCollectionService.dto.IndicatorResultDTO;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import com.trendmarket.DataCollectionService.repository.TechnicalIndicatorRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.Map;
import java.time.LocalDateTime;
import java.util.stream.Collectors;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Service
public class TechnicalIndicatorService {
    private static final Logger logger = LoggerFactory.getLogger(TechnicalIndicatorService.class);

    private final ObjectMapper objectMapper;
    private final StockRepository stockRepository;
    private final TechnicalIndicatorRepository indicatorRepository;
    private final ConcurrentHashMap<String, CompletableFuture<Integer>> pendingBatches =
            new ConcurrentHashMap<>();

    public TechnicalIndicatorService(
            ObjectMapper objectMapper,
            StockRepository stockRepository,
            TechnicalIndicatorRepository indicatorRepository
    ) {
        this.objectMapper = objectMapper;
        this.stockRepository = stockRepository;
        this.indicatorRepository = indicatorRepository;
    }

    public CompletableFuture<Integer> registerBatch(String ticker) {
        CompletableFuture<Integer> future = new CompletableFuture<>();
        CompletableFuture<Integer> previous = pendingBatches.putIfAbsent(ticker, future);
        if (previous != null) {
            throw new IllegalStateException("Indicator batch already pending for ticker: " + ticker);
        }
        return future;
    }

    public int awaitBatch(String ticker, CompletableFuture<Integer> future)
            throws InterruptedException, TimeoutException {
        try {
            return future.get(30, TimeUnit.MINUTES);
        } catch (TimeoutException exception) {
            pendingBatches.remove(ticker, future);
            throw exception;
        } catch (java.util.concurrent.ExecutionException exception) {
            throw new IllegalStateException("Indicator batch failed for ticker: " + ticker,
                    exception.getCause());
        }
    }

    public void cancelBatch(String ticker, CompletableFuture<Integer> future) {
        pendingBatches.remove(ticker, future);
        future.cancel(false);
    }

    public LocalDateTime getLatestIndicatorDatetime(String ticker) {
        return indicatorRepository.findTopByStock_TickerOrderByDatetimeDesc(ticker)
                .map(TechnicalIndicator::getDatetime)
                .orElse(null);
    }

    @Transactional
    public void saveResult(String payload) {
        long startedAt = System.nanoTime();
        String ticker = null;
        try {
            java.util.List<IndicatorResultDTO> results = objectMapper.readValue(
                    payload, new TypeReference<java.util.List<IndicatorResultDTO>>() {});
            if (results.isEmpty()) {
                logger.warn("Ignoring empty indicator batch");
                return;
            }
            ticker = results.get(0).getTicker();
            long distinctDatetimes = results.stream()
                    .map(IndicatorResultDTO::getDatetime)
                    .filter(java.util.Objects::nonNull)
                    .distinct()
                    .count();
            if (distinctDatetimes != results.size()) {
                throw new IllegalArgumentException(String.format(
                        "Indicator batch contains invalid or duplicate datetimes: ticker=%s, results=%d, distinctDatetimes=%d",
                        results.get(0).getTicker(), results.size(), distinctDatetimes));
            }
            Stock stock = stockRepository.findByTicker(results.get(0).getTicker())
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Stock not found for indicator result: " + results.get(0).getTicker()));
            logger.info(
                    "Persisting indicator batch: ticker={}, rows={}, firstDatetime={}, lastDatetime={}",
                    stock.getTicker(),
                    results.size(),
                    results.get(0).getDatetime(),
                    results.get(results.size() - 1).getDatetime()
            );
            for (IndicatorResultDTO result : results) {
                TechnicalIndicator indicator = indicatorRepository
                        .findByStockAndDatetime(stock, result.getDatetime())
                        .orElseGet(TechnicalIndicator::new);
                indicator.setStock(stock);
                indicator.setDatetime(result.getDatetime());
                indicator.setDateContinuity(result.isDateContinuity());
                indicator.setTwoCrows(result.isTwoCrows());
                indicator.setSma20(result.getSma20());
                indicator.setEma12(result.getEma12());
                indicator.setEma26(result.getEma26());
                indicator.setRsi(result.getRsi14());
                indicator.setMacd(result.getMacd());
                indicator.setMacdSignal(result.getMacdSignal());
                indicator.setMacdHistogram(result.getMacdHistogram());
                indicator.setBollingerUpper(result.getBollingerUpper());
                indicator.setBollingerLower(result.getBollingerLower());
                indicator.setBollingerWidth(result.getBollingerWidth());
                indicator.setAtr(result.getAtr14());
                indicator.setObv(result.getObv());
                indicatorRepository.save(indicator);
            }
            logger.info(
                    "Indicator batch processed: ticker={}, records={}, persistenceMs={}",
                    results.get(0).getTicker(),
                    results.size(),
                    elapsedMillis(startedAt)
            );
            logger.info(
                    "Indicator batch date range: ticker={}, firstDatetime={}, lastDatetime={}",
                    results.get(0).getTicker(),
                    results.get(0).getDatetime(),
                    results.get(results.size() - 1).getDatetime()
            );
            CompletableFuture<Integer> future = pendingBatches.remove(ticker);
            if (future != null) {
                future.complete(results.size());
            }
        } catch (Exception exception) {
            logger.error(
                    "Failed to save indicator result: payloadBytes={}, ticker={}, errorType={}, message={}",
                    payload.getBytes(java.nio.charset.StandardCharsets.UTF_8).length,
                    ticker,
                    exception.getClass().getSimpleName(),
                    exception.getMessage()
            );
            if (ticker != null) {
                CompletableFuture<Integer> future = pendingBatches.remove(ticker);
                if (future != null) {
                    future.completeExceptionally(exception);
                }
            }
        }
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }

    public Map<String, Boolean> getLatestDateContinuity() {
        return indicatorRepository.findAllByOrderByDatetimeDesc().stream()
                .filter(indicator -> indicator.getStock() != null)
                .collect(Collectors.toMap(
                        indicator -> indicator.getStock().getTicker(),
                        TechnicalIndicator::getDateContinuity,
                        (latest, ignored) -> latest,
                        LinkedHashMap::new
                ));
    }

    public Boolean getLatestDateContinuity(String ticker) {
        return indicatorRepository.findTopByStock_TickerOrderByDatetimeDesc(ticker)
                .map(TechnicalIndicator::getDateContinuity)
                .orElse(null);
    }
}
