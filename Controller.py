from datetime import datetime
import json

from Database import Database
from Message import Message
from Shelly import Shelly

from MySensorsConstants import *


def jsonKeys2int(x):
    if isinstance(x, dict):
        return {int(k): v for k, v in x.items()}
    return x


class Controller:

    def __init__(self, inLogger):
        self.logger = inLogger
        self.logger.debug(f"controller __init__")

        self.connected = -1
        # TODO: Add these as constants to a separate constants.py module
        self.thisDatabase = Database("controller.db", self.logger)
        all_gateways = self.thisDatabase.gatewaySubscribes()
        all_gateways.append("shellies")
        all_gateways.append("Control")
        self.thisMessage = Message("homeserver", 1883, 60, "controller",
                                   self.when_message, all_gateways,
                                   self.logger)

        for gateway_publishes in self.thisDatabase.gatewayPublishes():
            self.thisMessage.discover(gateway_publishes)

        self.this_shelly = Shelly(self.thisMessage, self.thisDatabase, self.logger)

        # This is the maximum time we will wait for a message
        # Should be half the mqtt timeout duration
        maxTimeout = 30
        nextTime = maxTimeout

        self.thisMessage.run_loop(maxTimeout)

        # Pick up from where we last left off
        lastSeconds = self.thisDatabase.getLastSeconds()
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # If we failed and have now started the next day, go back to midnight and re-run everything
        if lastSeconds > (now - midnight).seconds:
            lastSeconds = 86400

        while True:
            now = datetime.now()
            seconds = (now - midnight).seconds
            self.logger.debug(f"In loop, seconds={seconds}, lastSeconds={lastSeconds}")
            # This should handle midnight...
            if lastSeconds > 86399:
                self.logger.debug(f"In loop, Midnight crossed")
                lastSeconds = -1
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Only bother checking for actions if we have moved on from previous
            if seconds > lastSeconds:
                actions = self.thisDatabase.timedActionsFired(lastSeconds + 1, seconds)

                for actionRow in actions:
                    self.executeAction(actionRow)

                nextTime = self.thisDatabase.nextTriggerTime(seconds) - seconds
                if nextTime > maxTimeout:
                    nextTime = maxTimeout
                    if seconds + nextTime > 86399:
                        nextTime = 86399 - seconds

            lastSeconds = seconds
            self.thisDatabase.setLastSeconds(lastSeconds)
            self.thisMessage.run_loop(nextTime)

    # The callback for when a PUBLISH message is received from the server.
    def when_message(self, client, userdata, msg):
        self.logger.debug(f"controller when_message {client}, {userdata}, {msg}")
        msgPayload = str(msg.payload.decode("UTF-8"))
        self.logger.info(f"Read message {msg.topic} {msgPayload}")

        topic_split = msg.topic.split("/")
        msgPublishTopic = topic_split[0]
        msgNodeId = topic_split[1]
        msgSensorId = topic_split[2]
        msgCommand = topic_split[3]
        if len(topic_split) > 5:
            msgType = topic_split[5]
        # Leaving this in for now but need to remove at some point!
        # - really useful to see what is going on
        print(msg.topic+" "+msgPayload)

        if msgPublishTopic not in {"Control", "shellies"}:
            gateway = self.thisDatabase.gatewayFindFromSubscribeTopic(msgPublishTopic)
            self.thisDatabase.objectUpdate("Gateway", gateway["GatewayId"], {})

        # Process a message directly from a Shelly device or an internal command
        # Note that we have hard-coded the shelly device name and so may need to change if we add another
        # TODO Add a list of Shelly device names - probably in the Shelly class
        if msgPublishTopic == "shellies" and \
                (msgNodeId == "shelly2" or (msgCommand == COMMAND_INTERNAL and msgPayload == "")):
            self.this_shelly.process_message(msg)

        elif msgPublishTopic == "Control":
            self.process_control(msgSensorId, msgCommand, msgPayload)

        # Discover response
        elif ((msgCommand == COMMAND_INTERNAL) and
                (msgType == I_DISCOVER_RESPONSE)):
            self.processDiscoverResponse(gateway, msgNodeId, msgPayload)

        # Node presentation
        elif ((msgCommand == COMMAND_PRESENTATION) and
                ((msgType == S_ARDUINO_REPEATER_NODE)
              or (msgType == S_ARDUINO_NODE))):
            self.processNodePresentation(gateway, msgNodeId, msgType, msgPayload)

        # Sketch name (used as node name...)
        elif ((msgCommand == COMMAND_INTERNAL) and
                (msgType == I_SKETCH_NAME)):
            self.processSketchName(gateway, msgNodeId, msgPayload)

        # Sketch version (used as node name...)
        elif ((msgCommand == COMMAND_INTERNAL) and
                (msgType == I_SKETCH_VERSION)):
            self.processSketchVersion(gateway, msgNodeId, msgPayload)

        # Sensor presentation
        elif ((msgCommand == COMMAND_PRESENTATION) and
                (int(msgSensorId) < 255)):
            self.processSensorPresentation(gateway, msgNodeId, msgSensorId, msgType, msgPayload)

        elif msgType == '48':
            self.process_control(msgSensorId, msgCommand, msgPayload)

        # Sensor set
        elif msgCommand == COMMAND_SET:
            self.processSensorSet(gateway, msgNodeId, msgSensorId, msgType, msgPayload)

    def processDiscoverResponse(self, inGateway, inMyNode, inPayload):
        self.logger.debug(f"controller processDiscoverResponse {inGateway}, {inMyNode}, {inPayload}")
        # Make sure that the node exists - even if just a skeleton framework
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
        self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

        # Now request the node to present
        self.thisMessage.present(inGateway["PublishTopic"], inMyNode)

    def processNodePresentation(self, inGateway, inMyNode, inNodeType, inLibraryVersion):
        self.logger.debug(f"""controller processNodePresentation 
                          {inGateway}, {inMyNode}, {inNodeType}, {inLibraryVersion}""")
        # Update the Node with these details
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
        values["NodeType"] = inNodeType
        values["LibraryVersion"] = inLibraryVersion
        self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

    def processSketchName(self, inGateway, inMyNode, inSketchName):
        self.logger.debug(f"controller processSketchName {inGateway}, {inMyNode}, {inSketchName}")
        # Make sure that the node exists - even if just a skeleton framework
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
        values["NodeName"] = inSketchName
        self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

    def processSketchVersion(self, inGateway, inMyNode, inSketchVersion):
        self.logger.debug(f"controller processSketchVersion {inGateway}, {inMyNode}, {inSketchVersion}")
        # Make sure that the node exists - even if just a skeleton framework
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
        values["CodeVersion"] = inSketchVersion
        self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

    def processSensorPresentation(self, inGateway, inMyNode, inMySensor, inSensorType, inSensorName):
        self.logger.debug(f"controller processSensorPresentation {inGateway}, {inMyNode}, {inMySensor}, {inSensorType}, {inSensorName}")
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
        # This will update the last seen date time and create the node if not found
        nodeId = self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

        # Update the Sensor with these details
        values = {}
        values["NodeId"] = nodeId
        values["MySensorsSensorId"] = inMySensor
        values["SensorName"] = inSensorName
        values["SensorType"] = inSensorType
        self.thisDatabase.sensorCreateUpdate(nodeId, inMySensor, values)

    def process_control(self, in_sensor, in_command, in_payload):
        self.logger.debug(f"controller process_control {in_sensor}, {in_command}, {in_payload}")

        # This handles ISG sending HC or DHW programme
        if (in_sensor == "HC" or in_sensor == "DHW") and in_command == COMMAND_SET:
            self.thisDatabase.store_prog(in_sensor, json.loads(in_payload, object_hook=jsonKeys2int))

        elif in_command == COMMAND_SET:
            # Must be a sensor (by name) set from the UI
            self.process_sensor_set_from_ui(in_sensor, in_payload)

    def process_sensor_set_from_ui(self, in_sensor, in_payload):
        self.logger.debug(f"controller process_sensor_set_from_ui {in_sensor}, {in_payload}")

        payload = in_payload.split(",")
        value = payload[0]

        if len(payload) < 2:
            sensor_details = self.thisDatabase.find_sensor_by_name(in_sensor)
            self.thisMessage.set_sensor(sensor_details["PublishTopic"],
                                        sensor_details["MySensorsNodeId"],
                                        sensor_details["MySensorsSensorId"],
                                        sensor_details["VariableType"],
                                        value)

            # Update the Sensor with these details
            values = {"NodeId": sensor_details["NodeId"],
                      "MySensorsSensorId": sensor_details["MySensorsSensorId"],
                      "VariableType": sensor_details["VariableType"],
                      "CurrentValue": value}

            self.thisDatabase.sensorCreateUpdate(
                sensor_details["NodeId"], sensor_details["MySensorsSensorId"], values)

        else:
            time = payload[1]
            # Now need to generate a temporary trigger appropriately
            self.logger.debug(f"controller process_sensor_set_from_ui need to process trigger at {time}")

        return

    def processSensorSet(self, inGateway, inMyNode, inMySensor, inVariableType, inValue):
        self.logger.debug(f"controller processSensorSet {inGateway}, {inMyNode}, {inMySensor}, {inVariableType}, {inValue}")

        values = {"MySensorsNodeId": inMyNode, "GatewayId": inGateway["GatewayId"]}
        # This will update the last seen date time and create the node if not found
        nodeId = self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

        # Update the Sensor with these details
        values = {"NodeId": nodeId, "MySensorsSensorId": inMySensor, "VariableType": inVariableType,
                  "CurrentValue": inValue}
        self.thisDatabase.sensorCreateUpdate(nodeId, inMySensor, values)

    def executeAction(self, inAction):
        self.logger.debug(f"controller executeAction {inAction}")
        sensorDetails = self.thisDatabase.find_sensor_by_name(inAction["SensorName"])
        if sensorDetails is not None:
            self.thisMessage.set_sensor(
                    sensorDetails["PublishTopic"],
                    sensorDetails["MySensorsNodeId"],
                    sensorDetails["MySensorsSensorId"],
                    inAction["VariableType"],
                    inAction["SetValue"])
