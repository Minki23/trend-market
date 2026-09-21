package com.trendmarket.DataCollectionService.service;

import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.dto.StockDTO;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.integration.support.MessageBuilder;
import org.springframework.messaging.MessageChannel;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

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

    public Stock saveDTOToDatabase(StockDTO dto) {

        Optional<Stock> existingStock =
                stockRepository.findByTicker(dto.getTicker());

        if (existingStock.isPresent())
            return existingStock.get();

        Stock stock = dtoToStock(dto);
        stock.setTicker(dto.getTicker());

        return stockRepository.save(stock);
    }

    private static Stock dtoToStock(StockDTO dto){
        return Stock.builder()
                .ticker(dto.getTicker())
                .name(dto.getName())
                .tradeable(dto.isTradeable())
                .sector(dto.getSector())
                .sectorKey(dto.getSectorKey())
                .industry(dto.getIndustry())
                .industryKey(dto.getIndustryKey())
                .market(dto.getMarket())
                .quoteType(dto.getQuoteType())
                .address1(dto.getAddress1())
                .city(dto.getCity())
                .state(dto.getState())
                .zip(dto.getZip())
                .country(dto.getCountry())
                .region(dto.getRegion())
                .currency(dto.getCurrency())
                .financialCurrency(dto.getFinancialCurrency())
                .exchange(dto.getExchange())
                .fullExchangeName(dto.getFullExchangeName())
                .exchangeTimezoneName(dto.getExchangeTimezoneName())
                .exchangeTimezoneShortName(dto.getExchangeTimezoneShortName())
                .website(dto.getWebsite())
                .irWebsite(dto.getIrWebsite())
                .phone(dto.getPhone())
                .fullTimeEmployees(dto.getFullTimeEmployees())
                .longBusinessSummary(dto.getLongBusinessSummary())
                .messageBoardId(dto.getMessageBoardId())
                .language(dto.getLanguage())
                .typeDisp(dto.getTypeDisp())
                .quoteSourceName(dto.getQuoteSourceName())
                .build();
    }

    public List<Stock> fetchAllFromDatabase(){
        return stockRepository.findAll();
    }

    public void clearStocksTable(){
        stockRepository.deleteAll();
    }

    public Optional<Stock> fetchByTickerFromDatabase(String ticker){
        return stockRepository.findByTicker(ticker);
    }

    public void fetchByTickerFromAPI(String ticker){
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

    public Map<String,String> getAllNamesFromDatabase() {

        return stockRepository
                .findAll()
                .stream()
                .collect(Collectors.toMap(Stock::getTicker, Stock::getName));
    }

    public void fetchAllFromApi() {
        mqttOutboundChanel.send(
                MessageBuilder.withPayload("Download all stocks from API").build()
        );
    }
}
