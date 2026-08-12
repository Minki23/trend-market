package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;

@Entity
@Table(name = "stock_fundamentals")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StockFundamental {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long fundamentalId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(nullable = false)
    private LocalDate periodDate;

    private Double bookValue;

    private Double currentRatio;

    private Double quickRatio;

    private Double debtToEquity;

    private Double ebitda;

    private Double ebitdaMargins;

    private Double earningsGrowth;

    private Double earningsQuarterlyGrowth;

    private Double freeCashflow;

    private Double grossMargins;

    private Double grossProfits;

    private Double netIncomeToCommon;

    private Double operatingCashflow;

    private Double operatingMargins;

    private Double profitMargins;

    private Double returnOnAssets;

    private Double returnOnEquity;

    private Double revenueGrowth;

    private Double revenuePerShare;

    private Double totalCash;

    private Double totalCashPerShare;

    private Double totalDebt;

    private Double totalRevenue;
}