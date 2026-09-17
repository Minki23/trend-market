package com.trendmarket.DataCollectionService.repository;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface PriceRepository extends JpaRepository<StockPrice, Long> {
    
    Optional<List<StockPrice>> findByStock_StockId(Long StockId);
    boolean existsByStockAndDateTime(Stock stock, LocalDateTime dateTime);
}
