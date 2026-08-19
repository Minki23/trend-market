package com.trendmarket.DataCollectionService.mqtt;

import com.trendmarket.DataCollectionService.dto.PriceDTO;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.PriceService;
import com.trendmarket.DataCollectionService.service.StockService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class MqttMessageHandler {

    private final Logger logger = LoggerFactory.getLogger(MqttMessageHandler.class);

    private final ObjectMapper mapper;

    private final StockService stockService;

    private  final PriceService priceService;

    public MqttMessageHandler(
            ObjectMapper mapper,
            StockService stockService,
            PriceService priceService
    ) {
        this.mapper = mapper.copy().registerModule(new JavaTimeModule());
        this.stockService = stockService;
        this.priceService = priceService;
    }

    public void handle(String topic, String payload) {
        System.out.println("received message "+ topic);

        try {
            if (MqttTopics.STOCK.equals(topic)) {
                StockDTO stockDTO =
                        mapper.readValue(payload, StockDTO.class);
                stockService.createStock(stockDTO);
            }

            if (MqttTopics.PRICE.equals(topic)) {
                System.out.println("Received price");
                PriceDTO priceDTO =
                        mapper.readValue(payload, PriceDTO.class);
                priceService.createPrice(priceDTO);
            }

        } catch (JsonProcessingException e) {

            logger.error("Failed to parse MQTT message: {}", payload, e);
        }
    }
}