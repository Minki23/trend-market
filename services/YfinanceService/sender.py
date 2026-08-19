import asyncio
import atexit

import paho.mqtt.client as mqtt  # pyright: ignore[reportMissingImports]


class YfinanceSender:

    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.client = mqtt.Client()
        self._network_loop_started = False
        self._connect_lock = asyncio.Lock()
        self._publish_lock = asyncio.Lock()

        atexit.register(self.close)

    def _connect_sync(self):
        if self.client.is_connected():
            return

        if not self._network_loop_started:
            self.client.connect(
                self.hostname,
                self.port,
                keepalive=60
            )
            self.client.loop_start()
            self._network_loop_started = True
            return

        self.client.reconnect()

    async def _ensure_connected(self):
        async with self._connect_lock:
            await asyncio.to_thread(self._connect_sync)

    def _publish_sync(self, topic, message):
        result = self.client.publish(topic, message)
        result.wait_for_publish()

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise OSError(
                f"Failed to publish to topic '{topic}', rc={result.rc}"
            )

    async def send_message(self, topic, message):
        await self._ensure_connected()

        async with self._publish_lock:
            await asyncio.to_thread(
                self._publish_sync,
                topic,
                message
            )

    def close(self):
        if not self._network_loop_started:
            return

        if self.client.is_connected():
            self.client.disconnect()

        self.client.loop_stop()
        self._network_loop_started = False