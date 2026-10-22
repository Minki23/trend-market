package com.trendmarket.DataCollectionService.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class IndicatorResultDTO {
    private String ticker;
    private LocalDateTime datetime;
    private boolean dateContinuity;
    private boolean twoCrows;
}
