package com.trendmarket.DataCollectionService.controller;


import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.service.PriceService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/price")
public class PriceController {

    PriceService priceService;

    public PriceController(
            PriceService priceService
    ){
        this.priceService = priceService;
    }

    @PostMapping("/fetchAll")
    public void fetchAllPrices(){
        priceService.fetchAllPrices();
    }

    @GetMapping("/get/{stockId}")
    public Optional<List<StockPrice>> getAllofTicker(@PathVariable Long stockId){
        Optional<List<StockPrice>> prices = priceService.fetchPricesId(stockId);
        
        return prices;
    }
}
