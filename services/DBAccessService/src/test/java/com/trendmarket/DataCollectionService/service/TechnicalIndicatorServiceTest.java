package com.trendmarket.DataCollectionService.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.TechnicalIndicator;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import com.trendmarket.DataCollectionService.repository.TechnicalIndicatorRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class TechnicalIndicatorServiceTest {
    private StockRepository stockRepository;
    private TechnicalIndicatorRepository indicatorRepository;
    private TechnicalIndicatorService service;
    private Stock stock;

    @BeforeEach
    void setUp() {
        stockRepository = mock(StockRepository.class);
        indicatorRepository = mock(TechnicalIndicatorRepository.class);
        service = new TechnicalIndicatorService(
                new ObjectMapper().registerModule(new JavaTimeModule()),
                stockRepository,
                indicatorRepository
        );
        stock = new Stock("TEST", "Test", "Technology", "US");
        when(stockRepository.findByTicker("TEST")).thenReturn(Optional.of(stock));
        when(indicatorRepository.findByStockAndDatetime(any(), any())).thenReturn(Optional.empty());
    }

    @Test
    void savesEveryDateInAResultBatchAndCompletesPendingWaiter() throws Exception {
        CompletableFuture<Integer> pending = service.registerBatch("TEST");
        String payload = """
                [
                  {"ticker":"TEST","recordCount":2,"datetime":"2026-01-01T00:00:00","dateContinuity":true,"twoCrows":false,"sma20":null},
                  {"ticker":"TEST","recordCount":2,"datetime":"2026-01-02T00:00:00","dateContinuity":true,"twoCrows":false,"sma20":1.5}
                ]
                """;

        service.saveResult(payload);

        assertEquals(2, service.awaitBatch("TEST", pending));
        verify(indicatorRepository, times(2)).save(any(TechnicalIndicator.class));
    }

    @Test
    void rejectsDuplicateDatetimesAndFailsPendingWaiter() {
        CompletableFuture<Integer> pending = service.registerBatch("TEST");
        String payload = """
                [
                  {"ticker":"TEST","datetime":"2026-01-01T00:00:00"},
                  {"ticker":"TEST","datetime":"2026-01-01T00:00:00"}
                ]
                """;

        service.saveResult(payload);

        assertThrows(IllegalStateException.class, () -> service.awaitBatch("TEST", pending));
        verify(indicatorRepository, never()).save(any());
    }

    @Test
    void rejectsASecondPendingBatchForTheSameTicker() {
        service.registerBatch("TEST");

        assertThrows(IllegalStateException.class, () -> service.registerBatch("TEST"));
    }

    @Test
    void cancelBatchRemovesPendingBatch() {
        CompletableFuture<Integer> pending = service.registerBatch("TEST");

        service.cancelBatch("TEST", pending);

        assertTrue(pending.isCancelled());
        assertDoesNotThrow(() -> service.registerBatch("TEST"));
    }

    @Test
    void returnsLatestIndicatorDatetimeForTicker() {
        TechnicalIndicator indicator = new TechnicalIndicator();
        LocalDateTime latest = LocalDateTime.of(2026, 1, 2, 0, 0);
        indicator.setDatetime(latest);
        when(indicatorRepository.findTopByStock_TickerOrderByDatetimeDesc("TEST"))
                .thenReturn(Optional.of(indicator));

        assertEquals(latest, service.getLatestIndicatorDatetime("TEST"));
    }

    @Test
    void returnsNullWhenTickerHasNoIndicators() {
        when(indicatorRepository.findTopByStock_TickerOrderByDatetimeDesc("TEST"))
                .thenReturn(Optional.empty());

        assertNull(service.getLatestIndicatorDatetime("TEST"));
    }

    @Test
    void exposesLatestContinuityPerTicker() {
        TechnicalIndicator newest = new TechnicalIndicator();
        newest.setStock(stock);
        newest.setDatetime(LocalDateTime.of(2026, 1, 2, 0, 0));
        newest.setDateContinuity(false);
        TechnicalIndicator older = new TechnicalIndicator();
        older.setStock(stock);
        older.setDatetime(LocalDateTime.of(2026, 1, 1, 0, 0));
        older.setDateContinuity(true);
        when(indicatorRepository.findAllByOrderByDatetimeDesc()).thenReturn(List.of(newest, older));
        when(indicatorRepository.findTopByStock_TickerOrderByDatetimeDesc("TEST"))
                .thenReturn(Optional.of(newest));

        assertEquals(Boolean.FALSE, service.getLatestDateContinuity().get("TEST"));
        assertEquals(Boolean.FALSE, service.getLatestDateContinuity("TEST"));
    }
}
