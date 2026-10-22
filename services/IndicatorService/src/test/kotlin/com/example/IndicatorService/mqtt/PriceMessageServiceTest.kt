package com.example.IndicatorService.mqtt

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import org.springframework.integration.channel.DirectChannel
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import java.time.LocalDateTime

class PriceMessageServiceTest {
    private val service = PriceMessageService(
        ObjectMapper().registerKotlinModule(),
        DirectChannel()
    )

    @Test
    fun `date continuity allows weekends and rejects larger gaps`() {
        val continuous = listOf(
            price("2026-10-16T00:00:00"),
            price("2026-10-19T00:00:00")
        )
        val discontinuous = continuous + price("2026-10-23T00:00:00")

        assertTrue(service.checkDateContinuity(continuous))
        assertFalse(service.checkDateContinuity(discontinuous))
    }

    @Test
    fun `detects two crows pattern`() {
        val prices = listOf(
            price("2026-10-14T00:00:00", open = 100.0, close = 110.0),
            price("2026-10-15T00:00:00", open = 112.0, close = 106.0),
            price("2026-10-16T00:00:00", open = 109.0, close = 103.0)
        )

        assertTrue(service.checkTwoCrows(prices))
    }

    @Test
    fun `does not detect bullish sequence as two crows`() {
        val prices = listOf(
            price("2026-10-14T00:00:00", open = 100.0, close = 110.0),
            price("2026-10-15T00:00:00", open = 112.0, close = 116.0),
            price("2026-10-16T00:00:00", open = 117.0, close = 120.0)
        )

        assertFalse(service.checkTwoCrows(prices))
    }

    private fun price(
        date: String,
        open: Double = 100.0,
        close: Double = 101.0
    ) = PriceMessage(
        ticker = "TEST",
        datetime = LocalDateTime.parse(date),
        open = open,
        high = maxOf(open, close),
        low = minOf(open, close),
        close = close
    )
}
