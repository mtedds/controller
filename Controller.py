from datetime import datetime

from Database import Database
from Message import Message

from MySensorsConstants import *


class Controller:

    def __init__(self, inLogger):
        self.logger = inLogger
        self.logger.debug(f"controller __init__")

        self.connected = -1
        # TODO: Add these as constants to a separate constants.py module
        self.thisDatabase = Database("controller.db", self.logger)
        self.thisMessage = Message("homeserver", 1883, 60, "controller",
                                   self.when_message, self.thisDatabase.gatewaySubscribes(), self.logger)

        for gatewayPublishes in self.thisDatabase.gatewayPublishes():
            self.thisMessage.discover(gatewayPublishes)

        # This is the maximum time we will wait for a message
        # Should be half the mqtt timeout duration
        maxTimeout = 30
        nextTime = maxTimeout

        self.thisMessage.run_loop(maxTimeout)
        
        lastSeconds = self.thisDatabase.getLastSeconds()
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

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
        msgSplit = msg.topic.split("/")
        msgPublishTopic = msgSplit[0]
        msgNodeId = msgSplit[1]
        msgSensorId = msgSplit[2]
        msgCommand = msgSplit[3]
        msgType = msgSplit[5]
        msgPayload = str(msg.payload.decode("UTF-8"))
        self.logger.info(f"Read message {msg.topic} {msgPayload}")
        # Leaving this in for now but need to remove at some point!
        # - really useful to see what is going on
        print(msg.topic+" "+msgPayload)

        gateway = self.thisDatabase.gatewayFindFromSubscribeTopic(msgPublishTopic)
        self.thisDatabase.objectUpdate("Gateway", gateway["GatewayId"], {})

        # Discover response
        if ((msgCommand == COMMAND_INTERNAL) and
                (msgType == I_DISCOVER_RESPONSE)):
            self.processDiscoverResponse(gateway, msgNodeId, msgPayload)

        # Node presemtation
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

        # Sensor presemtation
        elif ((msgCommand == COMMAND_PRESENTATION) and
                (int(msgSensorId) < 255)):
            self.processSensorPresentation(gateway, msgNodeId, msgSensorId, msgType, msgPayload)

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

    def processSensorSet(self, inGateway, inMyNode, inMySensor, inVariableType, inValue):
        self.logger.debug(f"controller processSensorSet {inGateway}, {inMyNode}, {inMySensor}, {inVariableType}, {inValue}")
        values = {}
        values["MySensorsNodeId"] = inMyNode
        values["GatewayId"] = inGateway["GatewayId"]
    # This will update the last seen date time and create the node if not found
        nodeId = self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

        # Update the Sensor with these details
        values = {}
        values["NodeId"] = nodeId
        values["MySensorsSensorId"] = inMySensor
        values["VariableType"] = inVariableType
        values["CurrentValue"] = inValue
        self.thisDatabase.sensorCreateUpdate(nodeId, inMySensor, values)

    def executeAction(self, inAction):
        self.logger.debug(f"controller executeAction {inAction}")
        sensorDetails = self.thisDatabase.findSensorByName(inAction["SensorName"])
        if sensorDetails != None:
            self.thisMessage.setSensor(
                    sensorDetails["PublishTopic"],
                    sensorDetails["MySensorsNodeId"],
                    sensorDetails["MySensorsSensorId"],
                    inAction["VariableType"],
                    inAction["SetValue"])
