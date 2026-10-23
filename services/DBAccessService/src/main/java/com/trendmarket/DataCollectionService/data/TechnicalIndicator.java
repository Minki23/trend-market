package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "technical_indicators", uniqueConstraints = {
        @UniqueConstraint(name = "technical_indicator_stock_datetime",
                columnNames = {"stock_id", "datetime"})
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class TechnicalIndicator {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long indicatorId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "datetime", nullable = false)
    private LocalDateTime datetime;

    @Column(name = "date_continuity")
    private Boolean dateContinuity;

    @Column(name = "two_crows")
    private Boolean twoCrows;

    @Column(name = "sma_20")
    private Double sma20;

    @Column(name = "ema_12")
    private Double ema12;

    @Column(name = "ema_26")
    private Double ema26;

    private Double rsi;
    private Double macd;

    @Column(name = "macd_signal")
    private Double macdSignal;

    @Column(name = "macd_hist")
    private Double macdHistogram;

    @Column(name = "bollinger_upper")
    private Double bollingerUpper;

    @Column(name = "bollinger_lower")
    private Double bollingerLower;

    @Column(name = "bollinger_width")
    private Double bollingerWidth;

    private Double atr;
    private Long obv;
}
