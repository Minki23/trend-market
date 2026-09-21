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

    @Column(nullable = false, unique = true)
    private String ticker;

    @Column(nullable = false)
    private String name;

    private boolean tradeable;

    private String sector;

    private String sectorKey;

    private String industry;

    private String industryKey;

    private String market;

    private String quoteType;

    private String address1;

    private String city;

    private String state;

    private String zip;

    private String country;

    private String region;

    private String currency;

    private String financialCurrency;

    private String exchange;

    private String fullExchangeName;

    private String exchangeTimezoneName;

    private String exchangeTimezoneShortName;

    private String website;

    private String irWebsite;

    private String phone;

    private Integer fullTimeEmployees;

    @Column(columnDefinition = "TEXT")
    private String longBusinessSummary;

    private String messageBoardId;

    private String language;

    private String typeDisp;

    private String quoteSourceName;

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

    @Override
    public String toString() {
        return "Stock{" +
                "stockId=" + stockId +
                ", ticker='" + ticker + '\'' +
                ", name='" + name + '\'' +
                ", sector='" + sector + '\'' +
                ", industry='" + industry + '\'' +
                ", market='" + market + '\'' +
                '}';
    }
}