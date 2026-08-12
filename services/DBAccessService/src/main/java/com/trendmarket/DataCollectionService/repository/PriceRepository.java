package com.trendmarket.DataCollectionService.repository;

import com.trendmarket.DataCollectionService.data.StockPrice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PriceRepository extends JpaRepository<StockPrice, Long> {
}
