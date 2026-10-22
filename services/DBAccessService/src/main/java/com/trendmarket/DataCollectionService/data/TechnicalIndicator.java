package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "technical_indicators")
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

    private LocalDateTime datetime;

    @Column(name = "date_continuity")
    private Boolean dateContinuity;

    @Column(name = "two_crows")
    private Boolean twoCrows;
}
