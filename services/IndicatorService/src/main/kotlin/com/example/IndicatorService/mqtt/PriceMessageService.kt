package com.example.IndicatorService.mqtt

import com.fasterxml.jackson.core.JsonProcessingException
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue
import org.slf4j.LoggerFactory
import org.springframework.stereotype.Service
import org.springframework.integration.support.MessageBuilder
import org.springframework.integration.mqtt.support.MqttHeaders
import org.springframework.messaging.MessageChannel
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime

data class PriceMessage(
    val ticker: String? = null,
    val datetime: LocalDateTime? = null,
    val timestamp: LocalDateTime? = null,
    val open: Double? = null,
    val high: Double? = null,
    val low: Double? = null,
    val close: Double? = null,
    val volume: Long? = null
) {
    fun date(): LocalDate? = (datetime ?: timestamp)?.toLocalDate()
    fun dateTime(): LocalDateTime? = datetime ?: timestamp
}

data class IndicatorResult(
    val ticker: String,
    val recordCount: Int,
    val datetime: LocalDateTime?,
    val dateContinuity: Boolean,
    val twoCrows: Boolean,
    val sma20: Double?,
    val ema12: Double?,
    val ema26: Double?,
    val rsi14: Double?,
    val macd: Double?,
    val macdSignal: Double?,
    val macdHistogram: Double?,
    val bollingerUpper: Double?,
    val bollingerLower: Double?,
    val bollingerWidth: Double?,
    val atr14: Double?,
    val obv: Long?
)

@Service
class PriceMessageService(
    private val objectMapper: ObjectMapper,
    private val mqttOutboundChannel: MessageChannel
) {
    private val logger = LoggerFactory.getLogger(PriceMessageService::class.java)

    private companion object {
        const val RESULT_TOPIC = "indicator/result"
    }

    fun handle(payload: String) {
        val handlerStartedAt = System.nanoTime()
        logger.info("Received indicator batch: payloadBytes={}", payload.toByteArray().size)
        try {
            val prices = objectMapper.readValue<List<PriceMessage>>(payload)
                .sortedBy { it.dateTime() }
            if (prices.isEmpty()) {
                logger.warn("Ignoring empty price message")
                return
            }

            val ticker = prices.firstNotNullOfOrNull { it.ticker } ?: "unknown"
            logger.info("Starting indicator batch: ticker={}, records={}", ticker, prices.size)
            val calculationStartedAt = System.nanoTime()
            var dateContinuity = true
            val results = prices.indices.map { index ->
                val history = prices.subList(0, index + 1)
                if (index > 0) {
                    dateContinuity = dateContinuity &&
                        isContinuous(prices[index - 1], prices[index])
                }
                val indicators = calculateIndicators(history)
                IndicatorResult(
                    ticker = ticker,
                    recordCount = prices.size,
                    datetime = prices[index].dateTime(),
                    dateContinuity = dateContinuity,
                    twoCrows = checkTwoCrows(history),
                    sma20 = indicators.sma20,
                    ema12 = indicators.ema12,
                    ema26 = indicators.ema26,
                    rsi14 = indicators.rsi14,
                    macd = indicators.macd,
                    macdSignal = indicators.macdSignal,
                    macdHistogram = indicators.macdHistogram,
                    bollingerUpper = indicators.bollingerUpper,
                    bollingerLower = indicators.bollingerLower,
                    bollingerWidth = indicators.bollingerWidth,
                    atr14 = indicators.atr14,
                    obv = indicators.obv
                )
            }
            val calculationMillis = elapsedMillis(calculationStartedAt)
            logger.info(
                "Indicator batch calculated: ticker={}, inputRecords={}, resultRecords={}, calculationMs={}",
                ticker,
                prices.size,
                results.size,
                calculationMillis
            )

            mqttOutboundChannel.send(
                MessageBuilder.withPayload(objectMapper.writeValueAsString(results))
                    .setHeader(MqttHeaders.TOPIC, RESULT_TOPIC)
                    .build()
            )

            logger.info(
                "Indicator batch published: ticker={}, inputRecords={}, resultRecords={}, totalMs={}",
                ticker,
                prices.size,
                results.size,
                elapsedMillis(handlerStartedAt)
            )
        } catch (exception: JsonProcessingException) {
            logger.error(
                "Failed to parse price MQTT message: payloadBytes={}, errorType={}, message={}",
                payload.toByteArray().size,
                exception.javaClass.simpleName,
                exception.message
            )
        }
    }

    private fun elapsedMillis(startedAt: Long): Long =
        (System.nanoTime() - startedAt) / 1_000_000

    private fun calculateIndicators(prices: List<PriceMessage>): CalculatedIndicators {
        val validCloses = prices.map { it.close ?: return CalculatedIndicators.empty() }
        val sma20 = validCloses.takeLast(20).average().takeIf { validCloses.size >= 20 }
        val ema12 = ema(validCloses, 12)
        val ema26 = ema(validCloses, 26)
        val shortEmaSeries = emaSeries(validCloses, 12)
        val longEmaSeries = emaSeries(validCloses, 26)
        val macdSeries = shortEmaSeries.indices.mapNotNull { index ->
            val short = shortEmaSeries[index]
            val long = longEmaSeries.getOrNull(index)
            if (short != null && long != null) short - long else null
        }
        val macd = macdSeries.lastOrNull()
        val macdSignal = ema(macdSeries, 9)
        val rsi14 = calculateRsi(validCloses, 14)
        val bollinger = calculateBollinger(validCloses, 20)
        val atr14 = calculateAtr(prices, 14)
        val obv = calculateObv(prices)

        return CalculatedIndicators(
            sma20, ema12, ema26, rsi14, macd, macdSignal,
            macd?.let { value -> macdSignal?.let { value - it } },
            bollinger?.first, bollinger?.second, bollinger?.third, atr14, obv
        )
    }

    private fun ema(values: List<Double>, period: Int): Double? {
        return emaSeries(values, period).lastOrNull()
    }

    private fun emaSeries(values: List<Double>, period: Int): List<Double?> {
        if (values.size < period) return List(values.size) { null }
        val multiplier = 2.0 / (period + 1)
        var result = values.take(period).average()
        return buildList(values.size) {
            repeat(period - 1) { add(null) }
            add(result)
            values.drop(period).forEach {
                result = (it - result) * multiplier + result
                add(result)
            }
        }
    }

    private fun calculateRsi(values: List<Double>, period: Int): Double? {
        if (values.size <= period) return null
        val changes = values.zipWithNext { previous, current -> current - previous }
        var averageGain = changes.take(period).filter { it > 0 }.sum() / period
        var averageLoss = changes.take(period).filter { it < 0 }.sumOf { -it } / period
        changes.drop(period).forEach { change ->
            averageGain = (averageGain * (period - 1) + maxOf(change, 0.0)) / period
            averageLoss = (averageLoss * (period - 1) + maxOf(-change, 0.0)) / period
        }
        return if (averageLoss == 0.0) 100.0
        else 100.0 - (100.0 / (1.0 + averageGain / averageLoss))
    }

    private fun calculateBollinger(values: List<Double>, period: Int): Triple<Double, Double, Double>? {
        if (values.size < period) return null
        val window = values.takeLast(period)
        val mean = window.average()
        val deviation = kotlin.math.sqrt(window.map { (it - mean) * (it - mean) }.average())
        val upper = mean + 2 * deviation
        val lower = mean - 2 * deviation
        return Triple(upper, lower, if (mean == 0.0) 0.0 else (upper - lower) / mean)
    }

    private fun calculateAtr(prices: List<PriceMessage>, period: Int): Double? {
        if (prices.size < period + 1) return null
        val trueRanges = prices.zipWithNext().mapNotNull { (previous, current) ->
            val high = current.high ?: return@mapNotNull null
            val low = current.low ?: return@mapNotNull null
            val previousClose = previous.close ?: return@mapNotNull null
            maxOf(high - low, kotlin.math.abs(high - previousClose), kotlin.math.abs(low - previousClose))
        }
        return trueRanges.takeLast(period).takeIf { it.size == period }?.average()
    }

    private fun calculateObv(prices: List<PriceMessage>): Long? {
        if (prices.any { it.close == null || it.volume == null }) return null
        var obv = 0L
        prices.zipWithNext().forEach { (previous, current) ->
            if (current.close!! > previous.close!!) obv += current.volume!!
            else if (current.close < previous.close) obv -= current.volume!!
        }
        return obv
    }

    fun checkDateContinuity(prices: List<PriceMessage>): Boolean {
        return prices.zipWithNext().all { (previous, current) ->
            isContinuous(previous, current)
        }
    }

    private fun isContinuous(previous: PriceMessage, current: PriceMessage): Boolean {
        val previousDate = previous.date() ?: return false
        val currentDate = current.date() ?: return false
        return currentDate.isAfter(previousDate) &&
            Duration.between(previousDate.atStartOfDay(), currentDate.atStartOfDay()).toDays() <= 3
    }

    fun checkTwoCrows(prices: List<PriceMessage>): Boolean {
        if (prices.size < 3) {
            return false
        }

        val first = prices[prices.lastIndex - 2]
        val second = prices[prices.lastIndex - 1]
        val third = prices.last()
        return isTwoCrows(first, second, third)
    }

    private fun isTwoCrows(
        first: PriceMessage,
        second: PriceMessage,
        third: PriceMessage
    ): Boolean {
        val firstOpen = first.open ?: return false
        val firstClose = first.close ?: return false
        val secondOpen = second.open ?: return false
        val secondClose = second.close ?: return false
        val thirdOpen = third.open ?: return false
        val thirdClose = third.close ?: return false

        val firstIsLongBullish = firstClose > firstOpen
        val secondIsBearish = secondClose < secondOpen
        val thirdIsBearish = thirdClose < thirdOpen
        val secondGapsUp = secondOpen > firstClose
        val thirdOpensInsideSecondBody = thirdOpen < secondOpen && thirdOpen > secondClose
        val thirdClosesBelowSecond = thirdClose < secondClose
        val thirdRemainsAboveFirstOpen = thirdClose > firstOpen

        return firstIsLongBullish &&
            secondIsBearish &&
            thirdIsBearish &&
            secondGapsUp &&
            thirdOpensInsideSecondBody &&
            thirdClosesBelowSecond &&
            thirdRemainsAboveFirstOpen
    }
}

private data class CalculatedIndicators(
    val sma20: Double?,
    val ema12: Double?,
    val ema26: Double?,
    val rsi14: Double?,
    val macd: Double?,
    val macdSignal: Double?,
    val macdHistogram: Double?,
    val bollingerUpper: Double?,
    val bollingerLower: Double?,
    val bollingerWidth: Double?,
    val atr14: Double?,
    val obv: Long?
) {
    companion object {
        fun empty() = CalculatedIndicators(null, null, null, null, null, null, null, null, null, null, null, null)
    }
}
