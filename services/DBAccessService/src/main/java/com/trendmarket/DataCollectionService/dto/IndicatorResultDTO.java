package com.trendmarket.DataCollectionService.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class IndicatorResultDTO {
    private String ticker;
    private int recordCount;
    private LocalDateTime datetime;
    private boolean dateContinuity;
    private boolean twoCrows;
    private Double sma20;
    private Double ema12;
    private Double ema26;
    private Double rsi14;
    private Double macd;
    private Double macdSignal;
    private Double macdHistogram;
    private Double bollingerUpper;
    private Double bollingerLower;
    private Double bollingerWidth;
    private Double atr14;
    private Long obv;
}
