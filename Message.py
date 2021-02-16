import time
import sys
import paho.mqtt.client as mqtt
from functools import wraps

from MySensorsConstants import *


class Message:

    def __init__(self, inHost, inPort, inTimeout, inClient, in_when_message, in_gateways, inLogger):
        self.maxTimeout = inTimeout
        self.gateways = in_gateways
        self.logger = inLogger
        self.logger.debug(f"message __init__ {inHost}, {inPort}, {inTimeout}, {inClient}, {in_gateways}")

        self.mqttClient = mqtt.Client(inClient, True)
        self.mqttClient.on_connect = self.when_connect
        self.mqttClient.on_message = in_when_message

        self.connected = -1
        self.run_connect(inHost, inPort, inTimeout)

        while self.connected != 0:
            self.run_loop(5)

    def wrap_connection(func):
        @wraps(func)
        def function_wrapper(*args):
            self = args[0]
            self.logger.debug(f"message wrap_connection {func} {args}")
            rc = -1
            count = 0
            # TODO: This count should be configurable
            while (rc != 0) and (count < 5):
                count += 1
                try:
                    rc = func(*args)
                    break
                except ConnectionRefusedError as err:
                    self.logger.error(f"MQTT connection error code {err}")
                    time.sleep(self.maxTimeout/2)
                except:
                    self.logger.error(f"MQTT connection unexpected error: {sys.exc_info()[0]}")
            self.connected = rc
            return rc
        return function_wrapper

    def wrap_mqtt(func):
        @wraps(func)
        def function_wrapper(*args):
            self = args[0]
            self.logger.debug(f"message wrap_mqtt {func} {args}")
            rc = -1
            count = 0
            # TODO: This count should be configurable
            while (rc != 0) and (count < 5):
                count += 1
                try:
                    rc = func(*args)
                except ConnectionRefusedError as err:
                    self.logger.error(f"MQTT connection error code {err}")
                    time.sleep(self.maxTimeout/2)
                if rc > 0:
                    errmsg = mqtt.error_string(rc)
                    self.logger.error(f"Error in {func}: {rc} - {errmsg}")
                    # TODO: This should be half of the Timeout value but not in scope...
                    time.sleep(30)
                    self.run_reconnect()
            return(rc)
        return function_wrapper

    @wrap_connection
    def run_connect(self, inHost, inPort, inTimeout):
        self.logger.debug(f"message run_connect {inHost} {inPort} {inTimeout}")
        rc = self.mqttClient.connect(inHost, inPort, inTimeout)

        return rc

    @wrap_connection
    def run_reconnect(self):
        self.logger.debug(f"message run_reconnect")
        return self.mqttClient.reconnect()

    # The callback for when the client receives a CONNACK response from the server.
    def when_connect(self, client, userdata, flags, rc):
        self.logger.debug(f"message when_connect {client}, {userdata}, {flags}, {rc}")
        self.logger.info(f"Connected with result code {rc}")
        for gatewaySubscribe in self.gateways:
            self.subscribe(gatewaySubscribe)
        self.connected = rc

    @wrap_mqtt
    def run_loop(self, inTimeout):
        self.logger.debug(f"message run_loop {inTimeout}")
        rc = self.mqttClient.loop(inTimeout)
        if rc > 0:
            errmsg = mqtt.error_string(rc)
            self.logger.error(f"Error in Message.run_loop {rc} - {errmsg}")
            time.sleep(inTimeout/2)
        return(rc)

    def run_loop_forever(self):
        self.logger.debug(f"message run_loop_forever")
        self.mqttClient.loop_forever()

    def subscribe(self, inSubscription):
        self.logger.debug(f"message subscribe {inSubscription}")
        self.mqttClient.subscribe(inSubscription+"/#")

    def discover(self, inGatewayPublish):
        self.logger.debug(f"message discover {inGatewayPublish}")
#        self.mqttClient.publish("ISG-in/255/255/3/0/20")
        self.mqttClient.publish(inGatewayPublish + "/255/255/" + COMMAND_INTERNAL + "/0/" + I_DISCOVER_REQUEST, "")

    def present(self, inGatewayPublish, inMyNodeId):
        self.logger.debug(f"message present {inMyNodeId}")
#        self.mqttClient.publish("ISG-in/<Node>/255/3/0/19")
        self.mqttClient.publish(
                inGatewayPublish + "/" +
                inMyNodeId + "/255/" +
                COMMAND_INTERNAL + "/0/" +
                I_PRESENTATION,
                "")

    def set_sensor(self, inPublishTopic, inMySensorsNodeId, inMySensorsSensorId, inVariableType, inSetValue):
        self.logger.debug(f"message set_sensor {inPublishTopic}, {inMySensorsNodeId}, {inMySensorsSensorId}, {inVariableType}, {inSetValue}")
        msg = (inPublishTopic + "/" +
               str(inMySensorsNodeId) + "/" +
               str(inMySensorsSensorId) + "/" +
               str(COMMAND_SET) + "/0/" +
               str(inVariableType))
        self.logger.info(f"message set_sensor publishing {msg} {inSetValue}")
        self.mqttClient.publish(msg, str(inSetValue))

    def publish(self, in_topic, in_payload):
        self.logger.debug(f"message publish {in_topic}, {in_payload}")

        return self.mqttClient.publish(in_topic, in_payload)

    # This is used by the front end to send a message to the controller to set a sensor value
    def set_sensor_control(self, in_sensor_name, in_sensor_value):
        self.logger.debug(f"message publish {in_sensor_name}, {in_sensor_value}")

        msg = f"Control/0/{in_sensor_name}/{COMMAND_SET}/0/48"

        return self.publish(msg, in_sensor_value)