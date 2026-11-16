import paho.mqtt.client as mqtt
from enum import Enum, IntEnum, StrEnum

class MQTT_TOPICS(StrEnum):
    CLOCK_RC        = "rtsys/clockoffset_rc"

SERVER = 'wt.rtsys-lab.de'
MQTT_PORT = 1883


class NetworkWorkerMqtt:
    def __init__(self):
        # Use callback_api_version for paho-mqtt 2.0+ compatibility
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1
        )

        self.topic = MQTT_TOPICS.CLOCK_RC  # Default topic for clock offset data
        self.is_connected = False

        # Retry with exponential backoff (1s..5s) if the broker is unreachable or the connection drops
        self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=5)

        # Set up callbacks
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_publish = self._on_publish

        self.connect()

    def connect(self):
        try:
            # connect_async defers the TCP connection to the network loop thread,
            # so failures (e.g. no network at startup) are retried instead of raised here.
            # A short keepalive detects silent drops (e.g. interface change) quickly,
            # instead of waiting up to ~2x a long keepalive before noticing.
            self.mqtt_client.connect_async(SERVER, MQTT_PORT, keepalive=1)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.is_connected = False

    def _on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker (code: {rc})")
        if rc == 0:
            self.is_connected = True
        else:
            self.is_connected = False

    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        if rc != 0:
            print(f"Unexpected disconnection from MQTT broker (code: {rc})")
        else:
            print("Disconnected from MQTT broker")

    def _on_publish(self, client, userdata, mid):
        pass

    def send_data(self, data):
        if not self.is_connected:
            print("Cannot send data: MQTT client not connected")
            return False

        try:
            result = self.mqtt_client.publish(
                topic=self.topic,
                payload=data,
                qos=1,  # Quality of Service level 1 ensures message delivery at least once
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            else:
                print(f"Failed to publish MQTT message: {result.rc}")
                return False

        except Exception as e:
            print(f"Error publishing MQTT message: {e}")
            return False

    def disconnect(self):
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("MQTT client disconnected")
        except Exception as e:
            print(f"Error disconnecting MQTT client: {e}")

    def is_mqtt_connected(self):
        return self.is_connected