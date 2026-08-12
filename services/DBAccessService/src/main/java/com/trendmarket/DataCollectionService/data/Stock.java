package com.trendmarket.DataCollectionService.data;

import lombok.*;
import jakarta.persistence.*;

@Entity
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Getter
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

    public Stock(String ticker, String name, String sector, String market) {
        this.ticker = ticker;
        this.name = name;
        this.sector = sector;
        this.market = market;
    }

}