from MySensorsConstants import *

# This is just sent as part of the presentation message
software_version = 1.0


class Shelly:

    def __init__(self, in_message_handler, in_database, inLogger):
        self.logger = inLogger
        self.logger.debug(f"message __init__ {in_message_handler}, {in_database}, {inLogger}")

        self.message_handler = in_message_handler
        self.database = in_database

        self.gateway_id = self.database.gatewayFindFromSubscribeTopic("shellies")["GatewayId"]

        self.node_id = 0
        self.sensors = {"power": {"id": 0, "type": 13, "variable": 17, "name": "Current Watts"},
                        "voltage": {"id": 1, "type": 30, "variable": 38, "name": "Current Voltage"},
                        "total": {"id": 2, "type": 13, "variable": 18, "name": "Total Energy WH"},
                        "energy": {"id": 3, "type": 13, "variable": 28, "name": "Total Energy WMin"}}

        self.presentation()
        self.discover_response()

    # The callback for when a PUBLISH message is received from the server.
    def process_message(self, in_message):
        self.logger.debug(f"shelly process_message {in_message}")
        topic_split = in_message.topic.split("/")

        # These are for when it is a shelly originated message
        shelly_publish_topic = topic_split[0]
        # noinspection PyUnusedLocal
        shelly_device_name = topic_split[1]
        shelly_device_type = topic_split[2]
        # noinspection PyUnusedLocal
        shelly_sensor_id = topic_split[3]
        shelly_sensor = "unset"
        if shelly_device_type == "emeter":
            shelly_sensor = topic_split[4]
        sensor_value = str(in_message.payload.decode("UTF-8"))

        # This is if we are processing mySensors messages (eg. Presentation , discover, etc)
        msg_node_id = topic_split[1]
        # noinspection PyUnusedLocal
        msg_sensor_id = topic_split[2]
        msg_command = topic_split[3]
        if len(topic_split) > 5:
            msg_type = topic_split[5]

        # We are only processing sensor 0 - if we add the second sensor, we will need to change this...
        if shelly_sensor_id == "0" and shelly_sensor in self.sensors.keys():
            self.message_handler.set_sensor(shelly_publish_topic, self.node_id, self.sensors[shelly_sensor]["id"],
                                            self.sensors[shelly_sensor]["variable"], sensor_value)
        elif ((msg_node_id == "255") and
                (msg_command == COMMAND_INTERNAL) and
                (msg_type == I_DISCOVER_REQUEST)):
            self.discover_response()

        # Process presentation request from Controller
        elif ((msg_node_id == self.node_id) and
              (msg_command == COMMAND_INTERNAL) and
              (msg_type == I_PRESENTATION)):
            self.presentation()

    def presentation(self):
        self.logger.debug(f"shelly presentation")
        # Announce the Gateway as a repeater node
        self.message_handler.publish(f"shellies/{self.node_id}/255/0/0/18", software_version)

        # Announce the "sketch" and "version"
        self.message_handler.publish(f"shellies/{self.node_id}/255/3/0/11", "Shelly EM - shelly2")
        self.message_handler.publish(f"shellies/{self.node_id}/255/3/0/12", software_version)

        # Announce all of the sensors
        for sensor in self.sensors.keys():
            self.message_handler.publish(
                f"shellies/{self.node_id}/{self.sensors[sensor]['id']}/0/0/{self.sensors[sensor]['type']}",
                self.sensors[sensor]['name'])

    def discover_response(self):
        self.logger.debug(f"shelly discover_response")
        self.message_handler.publish(f"shellies/{self.node_id}/255/{COMMAND_INTERNAL}/0/{I_DISCOVER_RESPONSE}",
                                     self.node_id)
