package com.trendmarket.DataCollectionService.mqtt;

import com.fasterxml.jackson.core.type.TypeReference;
import com.trendmarket.DataCollectionService.dto.PriceDTO;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.service.PriceService;
import com.trendmarket.DataCollectionService.service.StockService;
import com.trendmarket.DataCollectionService.service.TechnicalIndicatorService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class MqttMessageHandler {

    private final Logger logger = LoggerFactory.getLogger(MqttMessageHandler.class);

    private final ObjectMapper mapper;

    private final StockService stockService;

    private  final PriceService priceService;
    private final TechnicalIndicatorService technicalIndicatorService;

    public MqttMessageHandler(
            ObjectMapper mapper,
            StockService stockService,
            PriceService priceService,
            TechnicalIndicatorService technicalIndicatorService
    ) {
        this.mapper = mapper.copy().registerModule(new JavaTimeModule());
        this.stockService = stockService;
        this.priceService = priceService;
        this.technicalIndicatorService = technicalIndicatorService;
    }

    public void handle(String topic, String payload) {
        try {
            if (MqttTopics.STOCK.equals(topic)) {
                List<StockDTO> stockDTOs =
                        mapper.readValue(payload, new TypeReference<>() {});
                for(StockDTO dto : stockDTOs){
                    stockService.saveDTOToDatabase(dto);
                }

            }

            if (MqttTopics.PRICE.equals(topic)) {

                List<PriceDTO> pricesList =
                        mapper.readValue(
                                payload,
                                new TypeReference<>() {
                                }
                        );
                priceService.pushPricesToDatabase(pricesList);
            }

            if (MqttTopics.INDICATOR_RESULT.equals(topic)) {
                technicalIndicatorService.saveResult(payload);
            }

        } catch (JsonProcessingException e) {

            logger.error(
                    "Failed to parse MQTT message: payloadBytes={}, errorType={}, message={}",
                    payload.getBytes(java.nio.charset.StandardCharsets.UTF_8).length,
                    e.getClass().getSimpleName(),
                    e.getMessage()
            );
        }
    }
}