import asyncio
import paho.mqtt.publish as publish


class YfinanceSender:

    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port

    async def send_message(self, topic, message):

        await asyncio.to_thread(
            publish.single,
            topic,
            message,
            hostname=self.hostname,
            port=self.port
        )