package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;

@Entity
@Table(name = "stock_analyst_data")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StockAnalystData {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long analystId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(nullable = false)
    private LocalDate date;

    private String recommendationKey;

    private Double recommendationMean;

    private Integer numberOfAnalystOpinions;

    private Double targetHighPrice;

    private Double targetLowPrice;

    private Double targetMeanPrice;

    private Double targetMedianPrice;
}