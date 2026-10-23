package com.trendmarket.DataCollectionService.controller;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.PriceService;
import com.trendmarket.DataCollectionService.service.StockService;
import com.trendmarket.DataCollectionService.service.TechnicalIndicatorService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.ResponseEntity;

@RestController
@RequestMapping("/stocks")
public class StockController {

    private final StockService stockService;
    private final PriceService priceService;
    private final TechnicalIndicatorService technicalIndicatorService;

    public StockController(
            StockService stockService,
            PriceService priceService,
            TechnicalIndicatorService technicalIndicatorService
    ) {
        this.stockService = stockService;
        this.priceService = priceService;
        this.technicalIndicatorService = technicalIndicatorService;
    }

    @PostMapping
    public Stock createStock(@RequestBody StockDTO body) {
        return stockService.saveDTOToDatabase(body);
    }

    @GetMapping("/{StockId}")
    public Optional<Stock> fetchByTicker(@PathVariable String ticker){
        return stockService.fetchByTickerFromDatabase(ticker);
    }

    @GetMapping
    public List<Stock> getAllStocks(){
        return stockService.fetchAllFromDatabase();
    }

    @GetMapping("/names")
    public Map<String,String> getAllStockNames(){
        return stockService.getAllNamesFromDatabase();
    }

    @GetMapping("/tickers")
    public List<String> getAllTickersFromDatabase(){return stockService.fetchAllTickersFromDatabase();}

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

    @PostMapping("/prices/indicators")
    public ResponseEntity<Map<String, String>> checkPriceIndicators() {
        boolean started = priceService.startIndicatorCheck();
        return ResponseEntity.accepted().body(Map.of(
                "status", started ? "started" : "already_running",
                "message", started
                        ? "Indicator calculation started"
                        : "Indicator calculation is already running"
        ));
    }

    @PostMapping("/indicators/calculate")
    public ResponseEntity<Map<String, String>> calculateIndicatorsForEveryStock() {
        boolean started = priceService.startIndicatorCheck();
        return ResponseEntity.accepted().body(Map.of(
                "status", started ? "started" : "already_running",
                "message", started
                        ? "Indicator calculation started"
                        : "Indicator calculation is already running"
        ));
    }

    @GetMapping("/prices/indicators/continuity")
    public Map<String, Boolean> getDateContinuity() {
        return technicalIndicatorService.getLatestDateContinuity();
    }

    @GetMapping("/prices/indicators/continuity/{ticker}")
    public Boolean getDateContinuity(@PathVariable String ticker) {
        return technicalIndicatorService.getLatestDateContinuity(ticker);
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