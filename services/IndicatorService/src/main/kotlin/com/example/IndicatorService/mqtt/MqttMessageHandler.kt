package com.example.IndicatorService.mqtt

import org.slf4j.LoggerFactory
import org.springframework.stereotype.Component

@Component
class MqttMessageHandler(
    private val priceMessageService: PriceMessageService
) {
    private val logger = LoggerFactory.getLogger(MqttMessageHandler::class.java)

    fun handle(topic: String, payload: String) {
        logger.info("Dispatching MQTT message: topic={}, payloadBytes={}", topic, payload.toByteArray().size)
        when (topic) {
            PRICE_CHECK_TOPIC -> priceMessageService.handle(payload)
            else -> logger.warn("Ignoring MQTT message from unsupported topic '{}'", topic)
        }
    }

    private companion object {
        const val PRICE_CHECK_TOPIC = "indicator/price-check"
    }
}
