import paho.mqtt.client as mqtt


class YfinanceSubscriber:

    def __init__(self, broker_address="localhost", broker_port=1883):
        self.broker_address = broker_address
        self.broker_port = broker_port

    def subscribe(self, topics, function):
        client = mqtt.Client()

        client.on_message = function

        client.connect(
            self.broker_address,
            self.broker_port
        )

        for topic in topics:
            client.subscribe(topic)

        client.loop_forever()