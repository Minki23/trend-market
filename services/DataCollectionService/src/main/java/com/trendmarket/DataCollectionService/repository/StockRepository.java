package com.trendmarket.DataCollectionService.repository;

import com.trendmarket.DataCollectionService.data.Stock;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface StockRepository extends JpaRepository<Stock, Long> {

    Optional<Stock> findByTicker(String ticker);

}
