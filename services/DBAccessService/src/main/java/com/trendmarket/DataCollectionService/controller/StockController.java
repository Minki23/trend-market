package com.trendmarket.DataCollectionService.controller;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.PriceService;
import com.trendmarket.DataCollectionService.service.StockService;
import org.springframework.messaging.MessageChannel;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/stocks")
public class StockController {

    private final StockService stockService;
    private final PriceService priceService;

    public StockController(
            StockService stockService,
            PriceService priceService
    ) {
        this.stockService = stockService;
        this.priceService = priceService;
    }

    @PostMapping
    public Stock createStock(@RequestBody StockDTO body) {
        return stockService.createStock(body);
    }

    @GetMapping("/{StockId}")
    public Optional<Stock> fetchByTicker(@PathVariable String ticker){
        Optional<Stock> response = stockService.getByTicker(ticker);
        return response;
    }

    @GetMapping
    public List<Stock> getAllStocks(){
        return stockService.getAll();
    }

    @GetMapping("/names")
    public Map<String,String> getAllStockNames(){
        return stockService.getAllNames();
    }

    @DeleteMapping
    public void removeAllStocks(){
        stockService.removeAll();
    }

    @GetMapping("/{ticker}")
    public void fetchFromApi(@PathVariable String ticker){
        stockService.fetchFromService(ticker);
    }

    @PostMapping("/fetch")
    public void fetchAllFromApi(){
        stockService.fetchAllFromApi();
    }

    @PostMapping("/prices")
    public void fetchAllPrices(){
        priceService.fetchAllPrices();
    }

    @GetMapping("/prices/{stockId}")
    public Optional<List<StockPrice>> getAllofTicker(@PathVariable Long stockId){

        return priceService.fetchPricesId(stockId);
    }
}