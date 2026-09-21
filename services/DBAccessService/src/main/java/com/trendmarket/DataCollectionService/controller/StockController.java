package com.trendmarket.DataCollectionService.controller;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.PriceService;
import com.trendmarket.DataCollectionService.service.StockService;
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
        return stockService.saveDTOToDatabase(body);
    }

    @GetMapping("/{StockId}")
    public Optional<Stock> fetchByTicker(@PathVariable String ticker){
        Optional<Stock> response = stockService.fetchByTickerFromDatabase(ticker);
        return response;
    }

    @GetMapping
    public List<Stock> getAllStocks(){
        return stockService.fetchAllFromDatabase();
    }

    @GetMapping("/names")
    public Map<String,String> getAllStockNames(){
        return stockService.getAllNamesFromDatabase();
    }

    @DeleteMapping
    public void removeAllStocks(){
        stockService.clearStocksTable();
    }

    @GetMapping("/{ticker}")
    public void fetchFromApi(@PathVariable String ticker){
        stockService.fetchByTickerFromAPI(ticker);
    }

    @PostMapping("/fetch")
    public void fetchAllFromApi(){
        stockService.fetchAllFromApi();
    }

    @PostMapping("/prices")
    public void fetchAllPrices(){
        priceService.pullPricesFromAPI();
    }

    @GetMapping("/prices")
    public List<StockPrice> getAll(){
        return priceService.fetchAllPricesFromDatabase();
    }

    @GetMapping("/prices/{stockId}")
    public Optional<List<StockPrice>> getAllofTicker(@PathVariable Long stockId){

        return priceService.fetchPricesById(stockId);
    }

    @DeleteMapping("/prices/clear")
    public void clearPricesData(){
        priceService.clearPricesTable();
    }
}