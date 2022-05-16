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
        self.thisDatabase = Database("/home/pi/controller/controller/controller.db", self.logger)
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
                    self.execute_action(actionRow)

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
            self.process_control(msgSensorId, msgCommand, int(msgType), msgPayload)

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

    def process_control(self, in_sensor, in_command, in_msg_type, in_payload):
        self.logger.debug(f"controller process_control {in_sensor}, {in_command}, {in_msg_type}, {in_payload}")

        if in_msg_type == 24:
            # Must be a sensor (by name) set from the UI
            self.process_sensor_set_from_ui(in_sensor, in_payload)
        elif in_msg_type == 25:
            self.process_trigger_set_from_ui(in_sensor, in_payload)

    def process_sensor_set_from_ui(self, in_sensor, in_payload):
        self.logger.debug(f"controller process_sensor_set_from_ui {in_sensor}, {in_payload}")

        if in_sensor == "DHW":
            return self.DHW_set(in_sensor, in_payload)

        # This is just a normal sensor set

        payload = in_payload.split(",")
        value = payload[0]

        # Clear out any Once triggers as they will just confuse everything - even if this is not timed!
        self.thisDatabase.delete_once_triggers(in_sensor)

        sensor_details = self.thisDatabase.find_sensor_by_name(in_sensor)

        # Send the command to switch it
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

        # Check if we need to switch it back at appropriate time or let the permanent timers do their job
        if len(payload) > 1:
            time = payload[1]
            if len(time) < 8:
                time += ":00"

            return_to_perm = False
            # Create matching inverse triggers against all the permanent triggers
            triggers = self.thisDatabase.find_triggers_until(in_sensor, datetime.now().strftime("%H:%M:%S"), time)
            for trigger in triggers:
                if trigger['Time'] == time:
                    return_to_perm = True
                elif trigger["SetValue"] != value:
                    self.thisDatabase.create_once_trigger(in_sensor, -1, f"{trigger['Time']}", value)

            # Now generate a final once trigger to switch it back at the right time
            if not return_to_perm:
                self.thisDatabase.create_once_trigger(in_sensor, -1, time, 1 - int(value))

        return

    def process_trigger_set_from_ui(self, in_sensor, in_payload):
        self.logger.debug(f"controller process_trigger_set_from_ui {in_sensor}, {in_payload}")

        payload = in_payload.split(" ")
        day = int(payload[0])
        group = int(payload[1])
        value = int(payload[2])
        time = payload[3]

        if in_sensor == "DHW":
            # val172 is Monday interval 1 - 3 intervals per day
            sensor_val = f"val{172 + day * 3 + group}"
            interval = self.thisDatabase.get_DHW_interval(day)

            new_isg_time = int((int(time[0:2]) * 60 + int(time[3:5])) / 15)

            publish_topic = self.thisDatabase.gatewayFindFromSubscribeTopic("ISG")["PublishTopic"]
            # Note that we assume the ISG is node 100 below...

            if value == 1:
                interval_end_time = int((int(interval[1]["Time"][0:2]) * 60 + int(interval[1]["Time"][3:5])) / 15)

                self.thisMessage.set_sensor(publish_topic, 100, sensor_val, 48,
                                            f"{new_isg_time:d};{interval_end_time:d}")
            else:
                interval_start_time = int((int(interval[0]["Time"][0:2]) * 60 + int(interval[0]["Time"][3:5])) / 15)

                self.thisMessage.set_sensor(publish_topic, 100, sensor_val, 48,
                                            f"{interval_start_time:d};{new_isg_time:d}")

        return self.thisDatabase.update_trigger(in_sensor, day, group, value, time)

    def DHW_set(self, in_sensor, in_payload):
        self.logger.debug(f"controller DHW_set {in_sensor}, {in_payload}")

        # Find all of the existing Replace triggers and execute them to clear back to "normal"
        for action in self.thisDatabase.find_replace_triggers(in_sensor):
            self.execute_action(action)

        payload = in_payload.split(",")
        value = int(payload[0])

        until_specified = False
        until_time = -1
        if len(payload) > 1:
            time = payload[1]
            until_specified = True
            until_time = int((int(time[0:2]) * 60 + int(time[3:5])) / 15)
            if len(time) < 8:
                time += ":00"

        now = datetime.now()
        # Monday is zero
        current_day_of_week = now.weekday()
        tomorrow_day_of_week = (current_day_of_week + 1) % 7

        # val172 is Monday interval 1 - 3 intervals per day (but we only use 1)
        sensor_val = f"val{172 + current_day_of_week * 3}"
        sensor_val_tomorrow = f"val{172 + tomorrow_day_of_week * 3}"

        current_interval = self.thisDatabase.get_DHW_interval(current_day_of_week)
        tomorrow_interval = self.thisDatabase.get_DHW_interval(tomorrow_day_of_week)

        interval_start_time = int(
            (int(current_interval[0]["Time"][0:2]) * 60 + int(current_interval[0]["Time"][3:5])) / 15)
        interval_end_time = int(
            (int(current_interval[1]["Time"][0:2]) * 60 + int(current_interval[1]["Time"][3:5])) / 15)
        tomorrow_interval_start_time = int(
            (int(tomorrow_interval[0]["Time"][0:2]) * 60 + int(tomorrow_interval[0]["Time"][3:5])) / 15)
        tomorrow_interval_end_time = int(
            (int(tomorrow_interval[1]["Time"][0:2]) * 60 + int(tomorrow_interval[1]["Time"][3:5])) / 15)
        current_time = int((now.hour * 60 + now.minute) / 15)

        new_start_time = interval_start_time
        new_end_time = interval_end_time
        new_tomorrow_start_time = tomorrow_interval_start_time
        new_tomorrow_end_time = tomorrow_interval_end_time

        self.logger.debug(f"controller DHW_set {interval_start_time}, {interval_end_time} {current_time} {int(value)}")

        publish_topic = self.thisDatabase.gatewayFindFromSubscribeTopic("ISG")["PublishTopic"]

        # This picks up all of the possibilities in turn!

        # Simple off
        if value == 0 and not until_specified:
            if current_time < interval_end_time:
                new_end_time = current_time

        # Simple on - boost for an hour
        if value == 1 and not until_specified:
            if current_time < interval_start_time:
                # Before the interval so bring start forward
                new_start_time = current_time
            elif current_time > interval_end_time - 3:
                # We are extending after the interval so add one hour
                new_end_time = current_time + 4
                if new_end_time > 96:
                    new_end_time = 96

        # Off until...
        if value == 0 and until_specified:
            if until_time > current_time:
                new_start_time = until_time
                if until_time > interval_end_time:
                    new_end_time = 96
                    new_tomorrow_start_time = 0
            else:
                # Off until tomorrow so just turn off today
                new_start_time = 128
                new_end_time = 128
                if until_time < tomorrow_interval_end_time:
                    new_tomorrow_start_time = until_time
                else:
                    # Off all the way through tomorrow's normal time as well!
                    new_tomorrow_start_time = 128
                    new_tomorrow_end_time = 128

        # On until...
        if value == 1 and until_specified:
            if current_time < interval_start_time:
                # Move the start time if we are before the interval
                new_start_time = current_time

            if until_time > current_time:
                # Just move the end to the until time
                new_end_time = until_time
            else:
                # Going over midnight...
                new_end_time = 96
                # Note until midnight is special case - don't want to update tomorrow interval
                if until_time > 0:
                    new_tomorrow_start_time = 0
                    new_tomorrow_end_time = until_time

        # Now apply the changes...
        if new_start_time != interval_start_time or new_end_time != interval_end_time:

            if new_start_time != interval_start_time:
                if new_start_time < 96:
                    new_start_time_hhmm = f"{int(new_start_time / 4):02d}:{(new_start_time % 4) * 15:02d}:00"
                else:
                    new_start_time_hhmm = "23:59:59"
                if new_start_time > interval_start_time:
                    self.thisDatabase.create_replace_trigger(in_sensor, current_day_of_week, new_start_time_hhmm,
                                                             current_interval[0]["TimedTriggerId"])
                else:
                    interval_start_time_hhmm = f"{int(interval_start_time / 4):02d}:{(interval_start_time % 4) * 15:02d}:00"
                    self.thisDatabase.create_replace_trigger(in_sensor, current_day_of_week, interval_start_time_hhmm,
                                                             current_interval[0]["TimedTriggerId"])
                update_values = {"Time": new_start_time_hhmm}
                self.thisDatabase.objectUpdate("TimedTrigger", current_interval[0]["TimedTriggerId"], update_values)

            if new_end_time != interval_end_time:
                if new_end_time < 96:
                    new_end_time_hhmm = f"{int(new_end_time / 4):02d}:{(new_end_time % 4) * 15:02d}:00"
                else:
                    new_end_time_hhmm = "23:59:59"
                if new_end_time > interval_end_time:
                    self.thisDatabase.create_replace_trigger(in_sensor, current_day_of_week, new_end_time_hhmm,
                                                             current_interval[1]["TimedTriggerId"])
                else:
                    interval_end_time_hhmm = f"{int(interval_end_time / 4):02d}:{(interval_end_time % 4) * 15:02d}:00"
                    self.thisDatabase.create_replace_trigger(in_sensor, current_day_of_week, interval_end_time_hhmm,
                                                             current_interval[1]["TimedTriggerId"])
                update_values = {"Time": new_end_time_hhmm}
                self.thisDatabase.objectUpdate("TimedTrigger", current_interval[1]["TimedTriggerId"], update_values)

            # Send the command to change the interval in the ISG
            # - should really find the MySensors Node Id from the database - only node for this gateway...
            self.thisMessage.set_sensor(publish_topic, 100, sensor_val, 48, f"{new_start_time:d};{new_end_time:d}")

            if new_tomorrow_start_time != tomorrow_interval_start_time or new_tomorrow_end_time != tomorrow_interval_end_time:

                if new_tomorrow_start_time != tomorrow_interval_start_time:
                    if new_tomorrow_start_time < 96:
                        new_tomorrow_start_time_hhmm = f"{int(new_tomorrow_start_time / 4):02d}:{(new_tomorrow_start_time % 4) * 15:02d}:00"
                    else:
                        new_tomorrow_start_time_hhmm = "23:59:59"
                    if new_tomorrow_start_time > tomorrow_interval_start_time:
                        self.thisDatabase.create_replace_trigger(in_sensor, tomorrow_day_of_week, new_tomorrow_start_time_hhmm,
                                                                 tomorrow_interval[0]["TimedTriggerId"])
                    else:
                        new_tomorrow_end_time_hhmm = f"{int(new_tomorrow_end_time / 4):02d}:{(new_tomorrow_end_time % 4) * 15:02d}:00"
                        self.thisDatabase.create_replace_trigger(in_sensor, tomorrow_day_of_week,
                                                                 new_tomorrow_end_time_hhmm,
                                                                 tomorrow_interval[0]["TimedTriggerId"])
                    update_values = {"Time": new_tomorrow_start_time_hhmm}
                    self.thisDatabase.objectUpdate("TimedTrigger", tomorrow_interval[0]["TimedTriggerId"], update_values)

                if new_tomorrow_end_time != tomorrow_interval_end_time:
                    if new_tomorrow_end_time < 96:
                        new_tomorrow_end_time_hhmm = f"{int(new_tomorrow_end_time / 4):02d}:{(new_tomorrow_end_time % 4) * 15:02d}:00"
                    else:
                        new_tomorrow_end_time_hhmm = "23:59:59"

                    self.thisDatabase.create_replace_trigger(in_sensor, tomorrow_day_of_week,
                                                             new_tomorrow_end_time_hhmm,
                                                             tomorrow_interval[1]["TimedTriggerId"])
                    update_values = {"Time": new_tomorrow_end_time_hhmm}
                    self.thisDatabase.objectUpdate("TimedTrigger", tomorrow_interval[1]["TimedTriggerId"], update_values)

                # Send the command to change the interval in the ISG
                # - should really find the MySensors Node Id from the database - only node for this gateway...
                self.thisMessage.set_sensor(publish_topic, 100, sensor_val_tomorrow, 48,
                                            f"{new_tomorrow_start_time:d};{new_tomorrow_end_time:d}")


    def processSensorSet(self, inGateway, inMyNode, inMySensor, inVariableType, inValue):
        self.logger.debug(f"controller processSensorSet {inGateway}, {inMyNode}, {inMySensor}, {inVariableType}, {inValue}")

        # This handles ISG sending HC or DHW programme
        if inMySensor == "HC" or inMySensor == "DHW":
            self.thisDatabase.store_prog(inMySensor, json.loads(inValue, object_hook=jsonKeys2int))
        else:
            values = {"MySensorsNodeId": inMyNode, "GatewayId": inGateway["GatewayId"]}
            # This will update the last seen date time and create the node if not found
            nodeId = self.thisDatabase.nodeCreateUpdate(inGateway["GatewayId"], inMyNode, values)

            # Update the Sensor with these details
            values = {"NodeId": nodeId, "MySensorsSensorId": inMySensor, "VariableType": inVariableType,
                      "CurrentValue": inValue}
            self.thisDatabase.sensorCreateUpdate(nodeId, inMySensor, values)

    def execute_action(self, in_action):
        self.logger.debug(f"controller execute_action {in_action}")

        if in_action["Status"] == "Active" or in_action["Status"] == "Once":
            sensor_details = self.thisDatabase.find_sensor_by_name(in_action["SensorName"])
            if sensor_details is not None:
                self.thisMessage.set_sensor(
                        sensor_details["PublishTopic"],
                        sensor_details["MySensorsNodeId"],
                        sensor_details["MySensorsSensorId"],
                        in_action["VariableType"],
                        in_action["SetValue"])

        if in_action["Status"] == "Replace":
            # Now update to the time from the Action
            updates = {"Time": in_action["SetValue"]}
            self.thisDatabase.objectUpdate("TimedTrigger", in_action["TimedTriggerToUpdate"], updates)

            # and send the updated interval back to the ISG
            # Assumes that on / off combinations are in strict numerical order - on then off
            filters = {"TimedTriggerId": in_action["TimedTriggerToUpdate"]}
            trigger = self.thisDatabase.object_find("TimedTrigger", filters)
            if trigger[0]["Description"][-2:] == "on":
                start_time = int((int(trigger[0]["Time"][0:2]) * 60 + int(trigger[0]["Time"][3:5])) / 15)
                filters = {"TimedTriggerId": in_action["TimedTriggerToUpdate"] + 1}
                off_trigger = self.thisDatabase.object_find("TimedTrigger", filters)
                end_time = int((int(off_trigger[0]["Time"][0:2]) * 60 + int(off_trigger[0]["Time"][3:5])) / 15)
            else:
                end_time = int((int(trigger[0]["Time"][0:2]) * 60 + int(trigger[0]["Time"][3:5])) / 15)
                filters = {"TimedTriggerId": in_action["TimedTriggerToUpdate"] - 1}
                on_trigger = self.thisDatabase.object_find("TimedTrigger", filters)
                start_time = int((int(on_trigger[0]["Time"][0:2]) * 60 + int(on_trigger[0]["Time"][3:5])) / 15)
            sensor_val = f"val{172 + in_action['Day'] * 3}"

            publish_topic = self.thisDatabase.gatewayFindFromSubscribeTopic("ISG")["PublishTopic"]

            # Send the command to switch it
            # - should really find the MySensors Node Id from the database - only node for this gateway...
            self.thisMessage.set_sensor(publish_topic, 100, sensor_val, 48,
                                        f"{start_time:d};{end_time:d}")

            # And clean up the Action - trigger will be removed below
            self.thisDatabase.object_delete("Action", in_action["ActionID"])

        if in_action["Status"] == "Once" or in_action["Status"] == "Replace":
            self.thisDatabase.object_delete("TimedTrigger", in_action["TimedTriggerId"])

