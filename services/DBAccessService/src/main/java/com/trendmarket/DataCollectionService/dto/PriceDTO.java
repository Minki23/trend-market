package com.trendmarket.DataCollectionService.dto;

import com.trendmarket.DataCollectionService.data.Stock;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PriceDTO {

    private String ticker;

    private Stock stock;

    private LocalDateTime datetime;

    private Double open;

    private Double high;

    private Double low;

    private Double close;

    private Long volume;

    private Double adjustedClose;

    public Long getStockId() {
        return this.stock != null ? this.stock.getStockId() : null;
    }

    public String getTicker() {
        if (this.ticker != null && !this.ticker.isBlank()) {
            return this.ticker;
        }

        return this.stock != null ? this.stock.getTicker() : null;
    }
}
