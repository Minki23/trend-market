package com.trendmarket.DataCollectionService.data;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import jakarta.persistence.*;
import lombok.NoArgsConstructor;

import java.util.Date;

@Entity
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StockPrice {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long prince_id;

    @ManyToOne
    @JoinColumn(name="stock_id", nullable = false)
    private Stock stock;

    @Column(nullable = false)
    private Date datetime;

    @Column(nullable = false)
    private double open;

    @Column(nullable = false)
    private double close;

    @Column(nullable = false)
    private double high;

    @Column(nullable = false)
    private double low;

    @Column(nullable = false)
    private double volume;
}
