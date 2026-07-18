package com.trendmarket.DataCollectionService.service;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class StockService {

    private final StockRepository stockRepository;

    public StockService(StockRepository stockRepository) {
        this.stockRepository = stockRepository;
    }

    public Stock createStock() {

        Stock stock = new Stock(
                "AAPL",
                "Apple Inc.",
                "Technology",
                "NASDAQ"
        );

        return stockRepository.save(stock);
    }

    public List<Stock> getAll(){
        return stockRepository.findAll();
    }
}
