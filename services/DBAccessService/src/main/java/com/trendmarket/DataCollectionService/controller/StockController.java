package com.trendmarket.DataCollectionService.controller;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.StockService;
import org.springframework.messaging.MessageChannel;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/stock")
public class StockController {

    private final StockService stockService;

    public StockController(
            StockService stockService
    ) {
        this.stockService = stockService;
    }

    @PostMapping
    public Stock createStock(@RequestBody StockDTO body) {
        return stockService.createStock(body);
    }
    @GetMapping
    public String hello(){
        return "Controller functions";
    }

    @RequestMapping("/find")
    public Optional<Stock> fetchByTicker(@RequestParam String ticker){
        Optional<Stock> response = stockService.getByTicker(ticker);
        return response;
    }

    @GetMapping("/getAll")
    public List<Stock> getAllStocks(){
        return stockService.getAll();
    }

    @GetMapping("/getAllNames")
    public Map<String,String> getAllStockNames(){
        return stockService.getAllNames();
    }

    @GetMapping("/getAllNamesDifferentThanTicker")
    public Map<String,String> getAllStockNamesDifferentThanTicker(){
        return stockService.getAllNamesDifferentThanTicker();
    }

    @DeleteMapping("/clear")
    public void removeAllStocks(){
        stockService.removeAll();
    }

    @PostMapping("/fetch")
    public void fetchFromApi(@RequestParam String ticker){
        stockService.fetchFromService(ticker);
    }

    @PostMapping("/all")
    public void fetchAllFromApi(){
        stockService.fetchAllFromApi();
    }
}