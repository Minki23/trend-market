package com.trendmarket.DataCollectionService.data;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Getter
@Table(name = "stock_prices", uniqueConstraints = {
	@UniqueConstraint(name = "stock_price_stock_datetime", columnNames = { "stock_id", "date_time" }) })
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

	@Column(name = "date_time")
	private LocalDateTime dateTime;

	@Column(name = "timestamp")
	private LocalDateTime timestamp;

	private Integer dayOfTheWeek;

	private Double open;

	private Double high;

	private Double low;

	private Double close;

	private Long volume;

	private Double adjustedClose;

	@Override
	public String toString() {
		return "StockPrice{" + "priceId=" + priceId + ", stock=" + stock + ", dateTime=" + dateTime + ", dayOfTheWeek="
				+ dayOfTheWeek + ", open=" + open + ", high=" + high + ", low=" + low + ", close=" + close + ", volume="
				+ volume + ", adjustedClose=" + adjustedClose + '}';
	}
}