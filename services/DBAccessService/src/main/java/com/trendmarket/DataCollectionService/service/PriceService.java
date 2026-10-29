package com.trendmarket.DataCollectionService.service;

import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.trendmarket.DataCollectionService.data.Stock;
import com.trendmarket.DataCollectionService.data.StockPrice;
import com.trendmarket.DataCollectionService.dto.PriceDTO;
import com.trendmarket.DataCollectionService.dto.IndicatorPriceDTO;
import com.trendmarket.DataCollectionService.repository.PriceRepository;
import com.trendmarket.DataCollectionService.repository.StockRepository;
import org.springframework.integration.support.MessageBuilder;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageDeliveryException;
import org.springframework.stereotype.Service;
import com.trendmarket.DataCollectionService.mqtt.MqttTopics;
import org.springframework.core.task.TaskExecutor;

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
	private final TaskExecutor indicatorTaskExecutor;
	private final TechnicalIndicatorService technicalIndicatorService;
	private final int indicatorBatchSize;
	private final java.util.concurrent.atomic.AtomicBoolean indicatorCalculationRunning =
			new java.util.concurrent.atomic.AtomicBoolean();

	public PriceService(StockService stockService, PriceRepository priceRepository,
			@Qualifier("mqttOutboundChannel") MessageChannel mqttOutboundChannel, StockRepository stockRepository,
			@Qualifier("indicatorTaskExecutor") TaskExecutor indicatorTaskExecutor,
			TechnicalIndicatorService technicalIndicatorService,
			@Value("${INDICATOR_BATCH_SIZE:1}") int indicatorBatchSize) {
		this.priceRepository = priceRepository;
		this.stockService = stockService;
		this.mqttOutboundChannel = mqttOutboundChannel;
		this.objectMapper = new ObjectMapper();
		objectMapper.registerModule(new JavaTimeModule());
		this.stockRepository = stockRepository;
		this.indicatorTaskExecutor = indicatorTaskExecutor;
		this.technicalIndicatorService = technicalIndicatorService;
		if (indicatorBatchSize <= 0) {
			throw new IllegalArgumentException("INDICATOR_BATCH_SIZE must be greater than zero");
		}
		this.indicatorBatchSize = indicatorBatchSize;
	}

	public void pullPricesFromAPI() {
		Map<String, String> stockNames = stockService.getAllNamesFromDatabase();
		sendPriceFetchRequest(stockNames.keySet());
	}

	public void pullPricesForStocksWithPrices() {
		sendPriceFetchRequest(new LinkedHashSet<>(priceRepository.findDistinctTickers()));
	}

	private void sendPriceFetchRequest(Collection<String> tickers) {
		String payload;
		try {
			payload = objectMapper.writeValueAsString(tickers);
		} catch (Exception e) {
			throw new IllegalStateException("Couldn't serialize price fetch tickers", e);
		}
		System.out.println("received call, pulling prices...");
		mqttOutboundChannel
				.send(MessageBuilder.withPayload(payload).setHeader(MqttHeaders.TOPIC, "fetch_prices").build());
	}

	public boolean startIndicatorCheck() {
		if (!indicatorCalculationRunning.compareAndSet(false, true)) {
			return false;
		}
		try {
			indicatorTaskExecutor.execute(this::requestIndicatorCheck);
			return true;
		} catch (RuntimeException exception) {
			indicatorCalculationRunning.set(false);
			throw exception;
		}
	}

	private void requestIndicatorCheck() {
		long requestStartedAt = System.nanoTime();
		logger.info("Indicator calculation started");
		int tickerCount = 0;
		int recordCount = 0;
		Map<String, PendingIndicatorBatch> pendingBatches = new LinkedHashMap<>();
		try {
			List<String> tickers = priceRepository.findDistinctTickers();
			logger.info(String.format("Indicator ticker batches found: count=%d, batchSize=%d",
					tickers.size(), indicatorBatchSize));
			for (String ticker : tickers) {
				long tickerStartedAt = System.nanoTime();
				try {
					logger.info(String.format("Loading indicator batch: ticker=%s", ticker));
					List<StockPrice> stockPrices = priceRepository.findByStock_TickerOrderByDateTimeAsc(ticker);
					logger.info(String.format("Indicator batch loaded: ticker=%s, records=%d",
							ticker, stockPrices.size()));
					LocalDateTime latestIndicatorDatetime =
							technicalIndicatorService.getLatestIndicatorDatetime(ticker);
					int existingRecordCount = 0;
					if (latestIndicatorDatetime != null) {
						existingRecordCount = (int) stockPrices.stream()
								.filter(price -> !price.getDateTime().isAfter(latestIndicatorDatetime))
								.count();
						stockPrices = stockPrices.stream()
								.filter(price -> price.getDateTime().isAfter(latestIndicatorDatetime))
								.toList();
					}
					logger.info(String.format(
							"Indicator records filtered: ticker=%s, latestIndicatorDatetime=%s, skipped=%d, new=%d",
							ticker, latestIndicatorDatetime, existingRecordCount, stockPrices.size()));
					if (stockPrices.isEmpty()) {
						logger.info(String.format("Indicator batch skipped: ticker=%s, no new records", ticker));
						continue;
					}
					List<IndicatorPriceDTO> prices = stockPrices.stream()
							.map(price -> new IndicatorPriceDTO(
									ticker,
									price.getDateTime(),
									price.getTimestamp(),
									price.getOpen(),
									price.getHigh(),
									price.getLow(),
									price.getClose(),
									price.getVolume()
							))
							.toList();
					String payload = objectMapper.writeValueAsString(prices);
					java.util.concurrent.CompletableFuture<Integer> resultFuture =
							technicalIndicatorService.registerBatch(ticker);
					logger.info(String.format("Sending indicator batch: ticker=%s, records=%d, payloadBytes=%d",
							ticker, prices.size(), payload.getBytes(java.nio.charset.StandardCharsets.UTF_8).length));
					try {
						mqttOutboundChannel.send(MessageBuilder.withPayload(payload)
								.setHeader(MqttHeaders.TOPIC, MqttTopics.INDICATOR_PRICE_CHECK)
								.build());
						pendingBatches.put(
								ticker,
								new PendingIndicatorBatch(resultFuture, tickerStartedAt, prices.size())
						);
						logger.info(String.format("Indicator batch sent: ticker=%s, pending=%d/%d",
								ticker, pendingBatches.size(), indicatorBatchSize));
					} catch (Exception exception) {
						technicalIndicatorService.cancelBatch(ticker, resultFuture);
						throw exception;
					}
					if (pendingBatches.size() >= indicatorBatchSize) {
						int[] persisted = awaitPendingBatches(pendingBatches);
						tickerCount += persisted[0];
						recordCount += persisted[1];
					}
				} catch (Exception tickerException) {
					logger.log(Level.SEVERE, String.format("Indicator batch failed: ticker=%s", ticker),
							tickerException);
				}
			}
			int[] persisted = awaitPendingBatches(pendingBatches);
			tickerCount += persisted[0];
			recordCount += persisted[1];
			logger.info(String.format(
				"Indicator requests prepared: tickers=%d, records=%d, totalMs=%d",
				tickerCount, recordCount,
				elapsedMillis(requestStartedAt)));
		} catch (Exception exception) {
			logger.log(java.util.logging.Level.SEVERE, "Indicator calculation request failed", exception);
		} finally {
			indicatorCalculationRunning.set(false);
		}
	}

	private int[] awaitPendingBatches(Map<String, PendingIndicatorBatch> pendingBatches) {
		int tickerCount = 0;
		int recordCount = 0;
		for (Map.Entry<String, PendingIndicatorBatch> entry : pendingBatches.entrySet()) {
			String ticker = entry.getKey();
			PendingIndicatorBatch pending = entry.getValue();
			try {
				int persistedRecords = technicalIndicatorService.awaitBatch(ticker, pending.future());
				logger.info(String.format(
						"Indicator batch persisted: ticker=%s, records=%d, batchMs=%d",
						ticker, persistedRecords, elapsedMillis(pending.startedAt())));
				tickerCount++;
				recordCount += pending.recordCount();
			} catch (Exception exception) {
				logger.log(Level.SEVERE, String.format("Indicator batch failed: ticker=%s", ticker),
						exception);
			}
		}
		pendingBatches.clear();
		return new int[] {tickerCount, recordCount};
	}

	private record PendingIndicatorBatch(
			java.util.concurrent.CompletableFuture<Integer> future,
			long startedAt,
			int recordCount
	) {}

	private long elapsedMillis(long startedAt) {
		return (System.nanoTime() - startedAt) / 1_000_000;
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
