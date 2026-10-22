package com.example.IndicatorService.mqtt

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import org.springframework.beans.factory.annotation.Qualifier
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.integration.channel.DirectChannel
import org.springframework.integration.core.MessageProducer
import org.springframework.integration.endpoint.EventDrivenConsumer
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter
import org.springframework.messaging.MessageChannel
import org.springframework.messaging.MessageHandler
import org.springframework.messaging.SubscribableChannel

@Configuration
class MqttConfig(
    @Value("\${mqtt.broker-url}") private val brokerUrl: String
) {
    companion object {
        private const val CLIENT_ID = "IndicatorService-in"
    }

    @Bean
    fun mqttInputChannel(): MessageChannel {
        return DirectChannel()
    }

    @Bean
    fun objectMapper(): ObjectMapper {
        return ObjectMapper()
            .registerKotlinModule()
            .registerModule(JavaTimeModule())
    }

    @Bean
    fun mqttInbound(): MessageProducer {
        val adapter = MqttPahoMessageDrivenChannelAdapter(
            brokerUrl,
            CLIENT_ID,
            "stock",
            "price",
            "indicator/price-check"
        )

        adapter.setCompletionTimeout(5000)
        adapter.setConverter(DefaultPahoMessageConverter())
        adapter.setQos(1)
        adapter.setOutputChannel(mqttInputChannel())

        return adapter
    }

    @Bean
    fun mqttOutboundChannel(): MessageChannel {
        return DirectChannel()
    }

    @Bean
    fun mqttOutbound(): MessageHandler {
        return MqttPahoMessageHandler(brokerUrl, "IndicatorService-out").apply {
            setAsync(true)
            setDefaultQos(1)
        }
    }

    @Bean
    fun mqttOutboundEndpoint(
        @Qualifier("mqttOutboundChannel") channel: SubscribableChannel,
        @Qualifier("mqttOutbound") handler: MessageHandler
    ): EventDrivenConsumer {
        return EventDrivenConsumer(channel, handler)
    }

    @Bean
    fun mqttInboundHandler(handler: MqttMessageHandler): MessageHandler {
        return MessageHandler { message ->
            val topic = message.headers["mqtt_receivedTopic"] as? String
                ?: throw IllegalStateException("Received MQTT message without a topic")
            handler.handle(topic, message.payload.toString())
        }
    }

    @Bean
    fun mqttInboundEndpoint(
        @Qualifier("mqttInputChannel") channel: SubscribableChannel,
        @Qualifier("mqttInboundHandler") handler: MessageHandler
    ): EventDrivenConsumer {
        return EventDrivenConsumer(channel, handler)
    }
}