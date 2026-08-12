package com.trendmarket.DataCollectionService.service;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.integration.support.MessageBuilder;
import org.springframework.messaging.MessageChannel;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Optional;

@Service
public class StockService {

    private final StockRepository stockRepository;

    private final MessageChannel mqttOutboundChanel;

    private final ObjectMapper objectMapper;

    public StockService(
            StockRepository stockRepository,
            @Qualifier("mqttOutboundChannel")
            MessageChannel mqttOutboundChannel,
            ObjectMapper objectMapper
            ) {
        this.stockRepository = stockRepository;
        this.mqttOutboundChanel = mqttOutboundChannel;
        this.objectMapper = objectMapper;
    }

    public Stock createStock(Stock body) {

        Stock stock = new Stock(
                body.getTicker(),
                body.getName(),
                body.getSector(),
                body.getMarket()
        );

        return stockRepository.save(stock);
    }

    public List<Stock> getAll(){
        return stockRepository.findAll();
    }

    public void removeAll(){
        stockRepository.deleteAll();
    }

    public Optional<Stock> getByTicker(String ticker){
        Optional<Stock> stock = stockRepository.findByTicker(ticker);
        return stock;
    }

    public void fetchFromService(String ticker){
        try {
            String json = objectMapper.writeValueAsString(ticker);

            mqttOutboundChanel.send(
                    MessageBuilder
                            .withPayload(json)
                            .build()
            );

        } catch (Exception e) {
            throw new RuntimeException("Could not serialize stock", e);
        }
    }
}
