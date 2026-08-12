package com.trendmarket.DataCollectionService.controller;


import com.trendmarket.DataCollectionService.service.PriceService;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/price")
public class PriceController {

    PriceService service;
}
