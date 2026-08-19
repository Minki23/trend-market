package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "stock_prices")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StockPrice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long priceId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "datetime", nullable = false)
    private LocalDateTime dateTime;

    @Column(name = "timestamp", nullable = false)
    private LocalDateTime timestamp;

    @Column(name = "date_time", nullable = false)
    private LocalDateTime legacyDateTime;

    private Double open;

    private Double high;

    private Double low;

    private Double close;

    private Long volume;

    private Double adjustedClose;
}