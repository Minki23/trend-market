package com.trendmarket.DataCollectionService.service;

import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.dto.PriceDTO;
import com.trendmarket.DataCollectionService.repository.PriceRepository;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import org.springframework.integration.support.MessageBuilder;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.beans.factory.annotation.Qualifier;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.messaging.MessageChannel;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

@Service
public class PriceService {

    private final PriceRepository priceRepository;
    private final StockService stockService;
    private final MessageChannel mqttOutboundChannel;
    private final ObjectMapper objectMapper;
    private final StockRepository stockRepository;
    private final Logger logger = Logger.getLogger(PriceService.class.getName());

    public PriceService(
            StockService stockService,
            PriceRepository priceRepository,
            @Qualifier("mqttOutboundChannel")
            MessageChannel mqttOutboundChannel,
            StockRepository stockRepository
    ){
        this.priceRepository = priceRepository;
        this.stockService = stockService;
        this.mqttOutboundChannel = mqttOutboundChannel;
        this.objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        this.stockRepository = stockRepository;
    }

    public void handleReceivePrice(){

    }

    public void processMessage(String payload) {
        //TODO
    }

    public void fetchAllPrices() {
        Map<String, String> stockNames = stockService.getAllNames();
        Set<String> tickers = stockNames.keySet();
        String payload = "";
        try {
            payload = objectMapper.writeValueAsString(tickers);
        }
        catch (Exception e){
            System.out.println(e);
        }
        System.out.println("received call, asking my man");
        mqttOutboundChannel.send(
                MessageBuilder
                        .withPayload(payload)
                        .setHeader(MqttHeaders.TOPIC, "fetch_prices")
                        .build()
        );
    }

    public StockPrice createPrice(PriceDTO dto) {
        Stock stock;
        var priceDateTime = dto.getDatetime();

        if (priceDateTime == null) {
            throw new RuntimeException("Missing required datetime value");
        }

        if (dto.getTicker() != null && !dto.getTicker().isBlank()) {
            stock = stockRepository.findByTicker(dto.getTicker())
                .orElseThrow(() ->
                    new RuntimeException("Stock not found by ticker: " + dto.getTicker())
                );
        } else {
            throw new RuntimeException("Missing stock identifier: stockId or stock.ticker is required");
        }

        StockPrice price = StockPrice.builder()
                .stock(stock)
            .dateTime(priceDateTime)
            .timestamp(priceDateTime)
            .legacyDateTime(priceDateTime)
                .open(dto.getOpen())
                .high(dto.getHigh())
                .low(dto.getLow())
                .close(dto.getClose())
                .volume(dto.getVolume())
                .adjustedClose(dto.getAdjustedClose())
                .build();

        return priceRepository.save(price);
    }
}
