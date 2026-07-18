package com.trendmarket.DataCollectionService.data;


import jakarta.persistence.*;

@Entity
@Table(name = "stocks")
public class Stock {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long stockId;

    @Column(nullable = false, unique = true)
    private String ticker;

    @Column(nullable = false)
    private String name;

    private String sector;

    private String market;

    // Required by JPA
    public Stock() {
    }

    public Stock(String ticker, String name, String sector, String market) {
        this.ticker = ticker;
        this.name = name;
        this.sector = sector;
        this.market = market;
    }

    public Long getStockId() {
        return stockId;
    }

    public void setStockId(Long stockId) {
        this.stockId = stockId;
    }

    public String getTicker() {
        return ticker;
    }

    public void setTicker(String ticker) {
        this.ticker = ticker;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSector() {
        return sector;
    }

    public void setSector(String sector) {
        this.sector = sector;
    }

    public String getMarket() {
        return market;
    }

    public void setMarket(String market) {
        this.market = market;
    }
}