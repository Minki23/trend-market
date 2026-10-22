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
    val close: Double? = null
) {
    fun date(): LocalDate? = (datetime ?: timestamp)?.toLocalDate()
    fun dateTime(): LocalDateTime? = datetime ?: timestamp
}

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
        try {
            val prices: List<PriceMessage> = objectMapper.readValue(payload)
            if (prices.isEmpty()) {
                logger.warn("Ignoring empty price message")
                return
            }

            val ticker = prices.firstNotNullOfOrNull { it.ticker } ?: "unknown"
            val datesAreContinuous = checkDateContinuity(prices)
            val hasTwoCrows = checkTwoCrows(prices)
            val result = IndicatorResult(
                ticker = ticker,
                datetime = prices.last().dateTime(),
                dateContinuity = datesAreContinuous,
                twoCrows = hasTwoCrows
            )

            mqttOutboundChannel.send(
                MessageBuilder.withPayload(objectMapper.writeValueAsString(result))
                    .setHeader(MqttHeaders.TOPIC, RESULT_TOPIC)
                    .build()
            )

            logger.info(
                "Processed {} price records for {}: dateContinuity={}, twoCrows={}",
                prices.size,
                ticker,
                datesAreContinuous,
                hasTwoCrows
            )
        } catch (exception: JsonProcessingException) {
            logger.error("Failed to parse price MQTT message: {}", payload, exception)
        }
    }

    fun checkDateContinuity(prices: List<PriceMessage>): Boolean {
        val dates = prices.map { it.date() ?: return false }
        return dates.zipWithNext().all { (previous, current) ->
            current.isAfter(previous) &&
                Duration.between(previous.atStartOfDay(), current.atStartOfDay()).toDays() <= 3
        }
    }

    fun checkTwoCrows(prices: List<PriceMessage>): Boolean {
        if (prices.size < 3) {
            return false
        }

        return prices.zipWithNext().windowed(2).any { window ->
            val first = window[0].first
            val second = window[0].second
            val third = window[1].second
            isTwoCrows(first, second, third)
        }
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

data class IndicatorResult(
    val ticker: String,
    val datetime: LocalDateTime?,
    val dateContinuity: Boolean,
    val twoCrows: Boolean
)
