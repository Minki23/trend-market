package com.trendmarket.DataCollectionService.service;

import com.trendmarket.DataCollectionService.repository.PriceRepository;
import org.springframework.stereotype.Service;

@Service
public class PriceService {

    private final PriceRepository repository;

    public PriceService(PriceRepository repository){
        this.repository = repository;
    }

    public void processMessage(String payload) {
        //TODO
    }
}
