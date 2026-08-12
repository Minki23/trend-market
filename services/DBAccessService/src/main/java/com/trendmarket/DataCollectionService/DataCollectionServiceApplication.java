package com.trendmarket.DataCollectionService;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.integration.annotation.IntegrationComponentScan;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.core.MessageProducer;
import org.springframework.integration.endpoint.EventDrivenConsumer;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.messaging.*;

@SpringBootApplication
@IntegrationComponentScan
public class DataCollectionServiceApplication {

	public static void main(String[] args) {

		new SpringApplicationBuilder(DataCollectionServiceApplication.class)
				.run(args);


//				(DataCollectionServiceApplication.class, args);
	}

	@Bean
	public MessageChannel mqttInputChannel() {
		return new DirectChannel();
	}

	@Bean
	public SubscribableChannel mqttOutboundChannel() {
		return new DirectChannel();
	}

	@Bean
	public MessageHandler mqttOutbound() {
		MqttPahoMessageHandler messageHandler =
				new MqttPahoMessageHandler(
						"tcp://mosquitto:1883",
						"DataCollectionService-out"
				);

		messageHandler.setAsync(true);
		messageHandler.setDefaultTopic("data");
		messageHandler.setDefaultQos(1);

		return messageHandler;
	}

	@Bean
	public EventDrivenConsumer mqttOutboundEndpoint(
			@Qualifier("mqttOutboundChannel") SubscribableChannel channel,
			@Qualifier("mqttOutbound") MessageHandler mqttOutbound) {

		return new EventDrivenConsumer(channel, mqttOutbound);
	}

	@Bean
	public MessageProducer inbound() {
		MqttPahoMessageDrivenChannelAdapter adapter =
				new MqttPahoMessageDrivenChannelAdapter(
						"tcp://mosquitto:1883",
						"DbAccessService-in",
						"database");
		adapter.setCompletionTimeout(5000);
		adapter.setConverter(new DefaultPahoMessageConverter());
		adapter.setQos(1);
		adapter.setOutputChannel(mqttInputChannel());
		return adapter;
	}

	@Bean
	@ServiceActivator(inputChannel = "mqttInputChannel")
	public MessageHandler handler() {
		return new MessageHandler() {

			@Override
			public void handleMessage(Message<?> message) throws MessagingException {
				System.out.println(message.getPayload());
			}

		};
	}

}
