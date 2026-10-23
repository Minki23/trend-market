package com.trendmarket.DataCollectionService;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
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
@EnableAsync
public class DataCollectionServiceApplication {

	public static void main(String[] args) {

		new SpringApplicationBuilder(DataCollectionServiceApplication.class)
				.run(args);


//				(DataCollectionServiceApplication.class, args);
	}

	@Bean(name = "indicatorTaskExecutor")
	public ThreadPoolTaskExecutor indicatorTaskExecutor() {
		ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
		executor.setCorePoolSize(1);
		executor.setMaxPoolSize(1);
		executor.setQueueCapacity(2);
		executor.setThreadNamePrefix("indicator-calculation-");
		executor.initialize();
		return executor;
	}

}
