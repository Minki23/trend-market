package com.trendmarket.DataCollectionService.controller;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.service.StockService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/stocks")
public class StockController {

    private final StockService stockService;

    public StockController(StockService stockService) {
        this.stockService = stockService;
    }

    @PostMapping
    public Stock createStock() {
        return stockService.createStock();
    }
    @GetMapping
    public String hello(){
        return "Controller functions";
    }

    @RequestMapping
    public String fetch_stocks(){

        return "";
    }

    @GetMapping("/abc")
    public List<Stock> getAllStocks(){
        return stockService.getAll();
    }
}