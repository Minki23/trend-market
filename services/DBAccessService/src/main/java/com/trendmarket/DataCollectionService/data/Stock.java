package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "stocks")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Stock {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long stockId;

    // =========================
    // Basic identification
    // =========================

    @Column(nullable = false, unique = true)
    private String ticker;

    @Column(nullable = false)
    private String name;

    // =========================
    // Classification
    // =========================

    private String sector;

    private String sectorKey;

    private String industry;

    private String industryKey;

    private String market;

    private String quoteType;

    // =========================
    // Location
    // =========================

    private String address1;

    private String city;

    private String state;

    private String zip;

    private String country;

    private String region;

    // =========================
    // Trading / exchange
    // =========================

    private String currency;

    private String financialCurrency;

    private String exchange;

    private String fullExchangeName;

    private String exchangeTimezoneName;

    private String exchangeTimezoneShortName;

    // =========================
    // Company information
    // =========================

    private String website;

    private String irWebsite;

    private String phone;

    private Integer fullTimeEmployees;

    @Column(columnDefinition = "TEXT")
    private String longBusinessSummary;

    // =========================
    // Other
    // =========================

    private String messageBoardId;

    private String language;

    private String typeDisp;

    private String quoteSourceName;

    // =========================
    // Constructor
    // =========================

    public Stock(
            String ticker,
            String name,
            String sector,
            String market
    ) {
        this.ticker = ticker;
        this.name = name;
        this.sector = sector;
        this.market = market;
    }
}