package com.example.IndicatorService.mqtt

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import org.springframework.integration.channel.DirectChannel
import org.springframework.integration.mqtt.support.MqttHeaders
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import java.time.LocalDateTime

class PriceMessageServiceTest {
    private val service = PriceMessageService(
        ObjectMapper().registerKotlinModule().registerModule(JavaTimeModule()),
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

    @Test
    fun `empty and incomplete price histories are handled safely`() {
        assertTrue(service.checkDateContinuity(emptyList()))
        assertFalse(service.checkTwoCrows(emptyList()))
        assertFalse(service.checkTwoCrows(listOf(price("2026-10-14T00:00:00"))))
        assertFalse(
            service.checkDateContinuity(
                listOf(price("2026-10-14T00:00:00"), price("2026-10-14T01:00:00"))
            )
        )
    }

    @Test
    fun `timestamp is used when datetime is absent`() {
        val timestampPrice = PriceMessage(
            ticker = "TEST",
            timestamp = LocalDateTime.parse("2026-10-14T00:00:00")
        )

        assertEquals(LocalDateTime.parse("2026-10-14T00:00:00"), timestampPrice.dateTime())
        assertEquals(java.time.LocalDate.parse("2026-10-14"), timestampPrice.date())
    }

    @Test
    fun `handle emits one result for every input price and calculates lookbacks`() {
        val channel = DirectChannel()
        val mapper = ObjectMapper().registerKotlinModule().registerModule(JavaTimeModule())
        val handlingService = PriceMessageService(mapper, channel)
        var output: String? = null
        channel.subscribe { message ->
            assertEquals("indicator/result", message.headers[MqttHeaders.TOPIC])
            output = message.payload.toString()
        }

        handlingService.handle(mapper.writeValueAsString((0 until 30).map { index ->
            price(
                "2026-01-01T00:00:00".let {
                    LocalDateTime.parse(it).plusDays(index.toLong()).toString()
                },
                open = 100.0 + index,
                close = 101.0 + index,
                volume = 1_000L + index
            )
        }))

        val results = mapper.readTree(output!!)
        assertEquals(30, results.size())
        assertTrue(results[0]["sma20"].isNull)
        assertFalse(results[19]["sma20"].isNull)
        assertFalse(results[11]["ema12"].isNull)
        assertFalse(results[25]["ema26"].isNull)
        assertFalse(results[14]["rsi14"].isNull)
        assertFalse(results[19]["bollingerUpper"].isNull)
        assertFalse(results[14]["atr14"].isNull)
        assertFalse(results[1]["obv"].isNull)
        assertEquals("TEST", results[29]["ticker"].asText())
    }

    @Test
    fun `handle reports two crows only on the ending candle date`() {
        val channel = DirectChannel()
        val mapper = ObjectMapper().registerKotlinModule().registerModule(JavaTimeModule())
        val handlingService = PriceMessageService(mapper, channel)
        var output: String? = null
        channel.subscribe { output = it.payload.toString() }
        val prices = listOf(
            price("2026-10-14T00:00:00", 100.0, 110.0),
            price("2026-10-15T00:00:00", 112.0, 106.0),
            price("2026-10-16T00:00:00", 109.0, 103.0),
            price("2026-10-17T00:00:00", 103.0, 104.0)
        )

        handlingService.handle(mapper.writeValueAsString(prices))

        val results = mapper.readTree(output!!)
        assertEquals(false, results[0]["twoCrows"].asBoolean())
        assertEquals(false, results[1]["twoCrows"].asBoolean())
        assertEquals(true, results[2]["twoCrows"].asBoolean())
        assertEquals(false, results[3]["twoCrows"].asBoolean())
    }

    private fun price(
        date: String,
        open: Double = 100.0,
        close: Double = 101.0,
        volume: Long? = 1_000L
    ) = PriceMessage(
        ticker = "TEST",
        datetime = LocalDateTime.parse(date),
        open = open,
        high = maxOf(open, close),
        low = minOf(open, close),
        close = close,
        volume = volume
    )
}
