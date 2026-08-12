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

}
