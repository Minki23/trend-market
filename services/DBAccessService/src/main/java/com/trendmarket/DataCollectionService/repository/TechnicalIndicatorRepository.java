package com.trendmarket.DataCollectionService.repository;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.TechnicalIndicator;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.List;

public interface TechnicalIndicatorRepository extends JpaRepository<TechnicalIndicator, Long> {
    Optional<TechnicalIndicator> findByStockAndDatetime(Stock stock, LocalDateTime datetime);
    List<TechnicalIndicator> findAllByOrderByDatetimeDesc();
    Optional<TechnicalIndicator> findTopByStock_TickerOrderByDatetimeDesc(String ticker);
}
