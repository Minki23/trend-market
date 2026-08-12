package com.trendmarket.DataCollectionService.mqtt;

import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.StockService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class MqttMessageHandler {

    private final Logger logger = LoggerFactory.getLogger(MqttMessageHandler.class);;

    private final ObjectMapper mapper = new ObjectMapper();

    private final StockService stockService;

    public void handle(String topic, String payload) {
        logger.info("Received MQTT message " + "Topic: " + topic + "Payload: " + payload);

        try {
            if (MqttTopics.STOCK.equals(topic)) {
                StockDTO stockDTO =
                        mapper.readValue(payload, StockDTO.class);
                stockService.createStock(stockDTO);
            }
        } catch (JsonProcessingException e) {

            logger.error("Failed to parse MQTT message: {}", payload, e);
        }
    }
}