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
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageDeliveryException;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import java.util.stream.Collectors;

@Service
public class PriceService {

	private final PriceRepository priceRepository;
	private final StockService stockService;
	private final MessageChannel mqttOutboundChannel;
	private final ObjectMapper objectMapper;
	private final StockRepository stockRepository;
	private final Logger logger = Logger.getLogger(PriceService.class.getName());
	private final Map<String, Stock> alreadyFound = new HashMap<>();

	public PriceService(StockService stockService, PriceRepository priceRepository,
			@Qualifier("mqttOutboundChannel") MessageChannel mqttOutboundChannel, StockRepository stockRepository) {
		this.priceRepository = priceRepository;
		this.stockService = stockService;
		this.mqttOutboundChannel = mqttOutboundChannel;
		this.objectMapper = new ObjectMapper();
		objectMapper.registerModule(new JavaTimeModule());
		this.stockRepository = stockRepository;
	}

	public void pullPricesFromAPI() {
		Map<String, String> stockNames = stockService.getAllNamesFromDatabase();
		Set<String> tickers = stockNames.keySet();
		String payload;
		try {
			payload = objectMapper.writeValueAsString(tickers);
		} catch (Exception e) {
			throw new RuntimeException("Couldn't map the payload");
		}
		System.out.println("received call, pulling prices...");
		mqttOutboundChannel
				.send(MessageBuilder.withPayload(payload).setHeader(MqttHeaders.TOPIC, "fetch_prices").build());
	}

	public StockPrice preparePriceDTO(PriceDTO dto) {
		Stock stock;

		LocalDateTime priceDateTime = dto.getDatetime();

		// If datetime is missing, fall back to timestamp (producer may send either)
		if (priceDateTime == null) {
			priceDateTime = dto.getTimestamp();
			if (priceDateTime == null) {
				throw new RuntimeException("Missing required datetime value");
			}
		}

		int dayOfTheWeek = priceDateTime.getDayOfWeek().getValue();

		if (alreadyFound.containsKey(dto.getTicker())) {
			stock = alreadyFound.get(dto.getTicker());
			return dtoToPrice(dto, stock, priceDateTime, dayOfTheWeek);
		}

		if (dto.getTicker() != null && !dto.getTicker().isBlank()) {
			stock = stockRepository.findByTicker(dto.getTicker())
					.orElseThrow(() -> new RuntimeException("Stock not found by ticker: " + dto.getTicker()));
			alreadyFound.put(dto.getTicker(), stock);
		} else {
			throw new RuntimeException("Missing stock identifier: stockId or stock.ticker is required");
		}
		return dtoToPrice(dto, stock, priceDateTime, dayOfTheWeek);
	}

	public void pushPricesToDatabase(List<PriceDTO> pricesDTOList) {
		List<StockPrice> priceList = new ArrayList<>();
		Map<String, LocalDateTime> latestDates = new HashMap<>();
		for (PriceDTO price : pricesDTOList) {
			StockPrice stockPrice = this.preparePriceDTO(price);

			String ticker = stockPrice.getStock().getTicker();

			if (stockPrice.getClose() == null) {
				System.out.println("Record without close value:" + stockPrice);
				continue;
			}

			LocalDateTime latestDate = latestDates.computeIfAbsent(ticker, t -> {
				final LocalDateTime DEFAULT_DATE = LocalDateTime.of(1900, 1, 1, 0, 0);
				LocalDateTime lastDate = priceRepository.findTopByStockOrderByDateTimeDesc(stockPrice.getStock())
						.map(StockPrice::getDateTime).orElse(DEFAULT_DATE);
				if (lastDate.equals(DEFAULT_DATE))
					System.out.println("No previous records found");
				else
					System.out.println("Latest current record for: " + ticker + " is: " + lastDate);
				return lastDate;
			});

			if (!stockPrice.getDateTime().isAfter(latestDate)) {
				continue;
			}

			priceList.add(stockPrice);
		}
		try {
			priceRepository.saveAllAndFlush(priceList);
			Map<String, List<Stock>> tickers = priceList.stream().map(StockPrice::getStock)
					.collect(Collectors.groupingBy(Stock::getTicker));
			if (tickers.isEmpty()) {
				logger.info("All of the records already exists");
			} else {
				logger.info(String.format("Saved %d records for %s", priceList.size(), tickers.keySet()));
			}
		} catch (Exception e) {
			// Batch insert failed; attempt per-record insert to isolate bad rows
			logger.log(Level.WARNING, "Batch insert failed: {0}. Falling back to per-record inserts.", e.getMessage());
			int saved = 0;
			for (StockPrice single : priceList) {
				try {
					// Defensive: ensure timestamp is set
					if (single.getTimestamp() == null) {
						single.setTimestamp(single.getDateTime());
					}
					priceRepository.saveAndFlush(single);
					saved++;
				} catch (Exception ex) {
					String ticker = "<unknown>";
					try {
						ticker = single.getStock().getTicker();
					} catch (Exception ignored) {
					}
					logger.log(Level.SEVERE, String.format("Failed to insert record for %s at %s: %s", ticker,
							single.getDateTime(), ex.getMessage()));
					// continue with next record
				}
			}
			logger.log(Level.INFO,
					String.format("Per-record insert complete: %d saved, %d failed", saved, priceList.size() - saved));
		}
	}

	public StockPrice dtoToPrice(PriceDTO dto, Stock stock, LocalDateTime priceDateTime, int dayOfTheWeek) {

		LocalDateTime timestampVal = dto.getTimestamp() != null ? dto.getTimestamp() : priceDateTime;

		return StockPrice.builder().stock(stock).dateTime(priceDateTime).timestamp(timestampVal)
				.dayOfTheWeek(dayOfTheWeek).open(dto.getOpen()).high(dto.getHigh()).low(dto.getLow())
				.close(dto.getClose()).volume(dto.getVolume()).adjustedClose(dto.getAdjustedClose()).build();
	}

	public Optional<List<StockPrice>> fetchPricesById(Long stockId) {
		return priceRepository.findByStock_StockId(stockId);
	}

	public void clearPricesTable() {
		priceRepository.deleteAllInBatch();
	}

	public List<StockPrice> fetchAllPricesFromDatabase() {
		return priceRepository.findAll();
	}
}
