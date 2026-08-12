package com.trendmarket.DataCollectionService.dto;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StockDTO {

    private String ticker;

    private String name;

    private String longName;

    private String shortName;

    private String displayName;

    private String symbol;

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

    private String longBusinessSummary;

    private String messageBoardId;

    private String language;

    private String typeDisp;

    private String quoteSourceName;
}