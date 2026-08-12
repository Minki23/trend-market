package com.trendmarket.DataCollectionService.mqtt;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.core.MessageProducer;
import org.springframework.integration.endpoint.EventDrivenConsumer;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageHandler;
import org.springframework.messaging.SubscribableChannel;
@Configuration
public class MqttConfig {

    private static final String BROKER_URL = "tcp://mosquitto:1883";

    @Bean
    public MessageChannel mqttInputChannel() {
        return new DirectChannel();
    }

    @Bean
    public SubscribableChannel mqttOutboundChannel() {
        return new DirectChannel();
    }

    // =========================
    // Subscriber
    // =========================

    @Bean
    public MessageProducer mqttInbound() {

        MqttPahoMessageDrivenChannelAdapter adapter =
                new MqttPahoMessageDrivenChannelAdapter(
                        BROKER_URL,
                        "DataCollectionService-in",
                        "stock"
                );

        adapter.setCompletionTimeout(5000);
        adapter.setConverter(new DefaultPahoMessageConverter());
        adapter.setQos(1);
        adapter.setOutputChannel(mqttInputChannel());

        return adapter;
    }

    // =========================
    // Message handler
    // =========================

    @Bean
    public MessageHandler mqttInboundHandler(
            MqttMessageHandler handler) {

        return message -> {
            System.out.println(
                    "========== MQTT MESSAGE RECEIVED =========="
            );

            System.out.println("Message: " + message);

            String topic = message.getHeaders()
                    .get("mqtt_receivedTopic", String.class);

            String payload = message.getPayload().toString();

            System.out.println("Topic: " + topic);
            System.out.println("Payload: " + payload);

            handler.handle(topic, payload);
        };
    }

    @Bean
    public EventDrivenConsumer mqttInboundEndpoint(
            @Qualifier("mqttInputChannel")
            SubscribableChannel channel,

            @Qualifier("mqttInboundHandler")
            MessageHandler mqttInboundHandler) {

        return new EventDrivenConsumer(
                channel,
                mqttInboundHandler
        );
    }

    // =========================
    // Publisher
    // =========================

    @Bean
    public MessageHandler mqttOutbound() {

        MqttPahoMessageHandler messageHandler =
                new MqttPahoMessageHandler(
                        BROKER_URL,
                        "DataCollectionService-out"
                );

        messageHandler.setAsync(true);
        messageHandler.setDefaultTopic(MqttTopics.FETCH);
        messageHandler.setDefaultQos(1);

        return messageHandler;
    }

    @Bean
    public EventDrivenConsumer mqttOutboundEndpoint(
            @Qualifier("mqttOutboundChannel")
            SubscribableChannel channel,

            @Qualifier("mqttOutbound")
            MessageHandler mqttOutbound) {

        return new EventDrivenConsumer(
                channel,
                mqttOutbound
        );
    }
}