package com.trendmarket.DataCollectionService.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.TechnicalIndicator;
import com.trendmarket.DataCollectionService.dto.IndicatorResultDTO;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import com.trendmarket.DataCollectionService.repository.TechnicalIndicatorRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class TechnicalIndicatorService {
    private static final Logger logger = LoggerFactory.getLogger(TechnicalIndicatorService.class);

    private final ObjectMapper objectMapper;
    private final StockRepository stockRepository;
    private final TechnicalIndicatorRepository indicatorRepository;

    public TechnicalIndicatorService(
            ObjectMapper objectMapper,
            StockRepository stockRepository,
            TechnicalIndicatorRepository indicatorRepository
    ) {
        this.objectMapper = objectMapper;
        this.stockRepository = stockRepository;
        this.indicatorRepository = indicatorRepository;
    }

    public void saveResult(String payload) {
        try {
            IndicatorResultDTO result = objectMapper.readValue(payload, IndicatorResultDTO.class);
            Stock stock = stockRepository.findByTicker(result.getTicker())
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Stock not found for indicator result: " + result.getTicker()));
            TechnicalIndicator indicator = indicatorRepository
                    .findByStockAndDatetime(stock, result.getDatetime())
                    .orElseGet(TechnicalIndicator::new);
            indicator.setStock(stock);
            indicator.setDatetime(result.getDatetime());
            indicator.setDateContinuity(result.isDateContinuity());
            indicator.setTwoCrows(result.isTwoCrows());
            indicatorRepository.save(indicator);
        } catch (Exception exception) {
            logger.error("Failed to save indicator result: {}", payload, exception);
        }
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
