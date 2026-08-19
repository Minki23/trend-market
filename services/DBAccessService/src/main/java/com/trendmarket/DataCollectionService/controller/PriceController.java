package com.trendmarket.DataCollectionService.controller;


import com.trendmarket.DataCollectionService.service.PriceService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
}
