import paho.mqtt.subscribe as subscribe

class YfinanceSubscriber:
    def __init__(self, broker_address="tcp://localhost", broker_port=1883):
        self.broker_address = broker_address
        self.broker_port = broker_port
    
    def subscribe(self, topic, function):
        subscribe.callback(
            function,
            topic,
            hostname=self.broker_address,
            port=self.broker_port
        )
