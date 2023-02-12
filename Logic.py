from datetime import datetime
from datetime import timedelta
from MySensorsConstants import *

# This class is used to handle all sensor logic, eg. when turn radiators on, make sure HC is on


class Logic:

    def __init__(self, in_message_handler, in_database, inLogger):
        self.logger = inLogger
        self.logger.debug(f"message __init__ {in_message_handler}, {in_database}, {inLogger}")

        self.message_handler = in_message_handler
        self.database = in_database

        self.logic_methods = {
            'Ensuite humidity': [self.logic_fan_boost,
                                 ["Ensuite fan control relay",
                                  "Ensuite fan boost relay",
                                  "Ensuite light switch",
                                  "Ensuite humidity"]],
            'Ensuite light switch': [self.logic_fan_boost,
                                     ["Ensuite fan control relay",
                                      "Ensuite fan boost relay",
                                      "Ensuite light switch",
                                      "Ensuite humidity"]],
            'Ensuite fan boost relay': [self.logic_fan_boost,
                                        ["Ensuite fan control relay",
                                         "Ensuite fan boost relay",
                                         "Ensuite light switch",
                                         "Ensuite humidity"]],
            'Utility heating': [self.logic_heat_control,
                                ["Utility ufloor relay", ]]
        }

        # This initialises all of the humidity boost flags
        self.humidity_boost = {}
        for sensor in self.logic_methods:
            if "humidity" in sensor:
                self.humidity_boost[sensor] = 0

    # Find the sensor, check if it has a function and then call it
    def run_sensor_set_logic(self, in_sensor_id, in_sensor_value):
        self.logger.debug(f"logic run_sensor_set_logic {in_sensor_id} {in_sensor_value}")

        sensor = self.database.object_find("Sensor", {"SensorId": in_sensor_id})
        if len(sensor) == 1:
            if sensor[0]["SensorName"] in self.logic_methods:
                # Call the appropriate method with the sensor name, value and arguments defined above
                # TODO: Drop the id, name and value from the arguments and have the methdd use the sensor dictionary
                self.logic_methods[sensor[0]["SensorName"]][0](sensor[0],
                                                               in_sensor_id, sensor[0]["SensorName"], in_sensor_value,
                                                               self.logic_methods[sensor[0]["SensorName"]][1])

    def logic_heat_control(self, in_sensor, in_sensor_id, in_sensor_name, in_sensor_value, in_arguments):
        # This function is called for any change to a climate sensor,
        # ie. Switch on / off, temperature change, set temperature change

        # Note that arguments are:
        # 1 = Relay to control heating on / off
        self.logger.debug(f"logic logic_heat_control {in_sensor_id} {in_sensor_name} {in_sensor_value} {in_arguments}")

        on_off_relay = in_arguments[0]

        # Depends which sensor we have received...
        self.logger.debug(f"logic logic_heat_control VariableType {in_sensor['VariableType']} = {V_HVAC_FLOW_STATE}")

        # The state (heat on / off / auto / ...) can be set independently (UI) or by this logic
        # The logic will set the state and the node will then confirm that change of state which is picked up here
        # So sequence is: temp change
        #                 -> message node to switch state to off (this could be directly from UI)
        #                 -> node responds state changed to off
        #                 -> message collected here
        #                 -> tell relay to turn off
        # Same for set point change and on / off
        if int(in_sensor["VariableType"]) == V_HVAC_FLOW_STATE:
            if in_sensor_value == "Off":
                self.set_sensor_by_name(on_off_relay, V_STATUS, "0")
            elif in_sensor_value == "HeatOn" or in_sensor_value == "AutoChangeOver":
                self.set_sensor_by_name(on_off_relay, V_STATUS, "1")

        # See if we need to message node to change state
        elif int(in_sensor["VariableType"]) == V_HVAC_SETPOINT_HEAT or int(in_sensor["VariableType"]) == V_TEMP:
            set_temp = float(self.database.get_sensor_value_by_name_type(in_sensor_name, V_HVAC_SETPOINT_HEAT))
            current_temp = float(self.database.get_sensor_value_by_name_type(in_sensor_name, V_TEMP))
            hysteresis = self.database.get_state_by_name("Temperature hysteresis")

            if current_temp > set_temp + hysteresis:
                # Reached temperature
                self.set_sensor_by_name(on_off_relay, V_HVAC_FLOW_STATE, "Off")
            elif current_temp < set_temp - hysteresis:
                # Need to warm up again
                self.set_sensor_by_name(on_off_relay, V_HVAC_FLOW_STATE, "HeatOn")

    def logic_fan_boost(self, in_sensor, in_sensor_id, in_sensor_name, in_sensor_value, in_arguments):
        # This function is called for a humidity change or a light switch change

        # Note that arguments are:
        # 1 = Relay that is set on when we are controlling the fan (off = manual)
        # 2 = Relay to set to switch boost on / off
        # 3 = Sensor for light switch on / off
        # 4 = Humidity sensor
        self.logger.debug(f"logic logic_fan_boost {in_sensor_id} {in_sensor_name} {in_sensor_value} {in_arguments}")

        control_relay = in_arguments[0]
        boost_relay = in_arguments[1]
        light_switch = in_arguments[2]
        humidity_sensor = in_arguments[3]

        if "humidity" in in_sensor_name:
            humidity = float(in_sensor_value)
            light = int(self.database.get_sensor_value_by_name(light_switch))
            boost = int(self.database.get_sensor_value_by_name(boost_relay))
            sensor = "humidity"
        elif "light" in in_sensor_name:
            humidity = float(self.database.get_sensor_value_by_name(humidity_sensor))
            light = int(in_sensor_value)
            boost = int(self.database.get_sensor_value_by_name(boost_relay))
            sensor = "light"
        else:
            humidity = float(self.database.get_sensor_value_by_name(humidity_sensor))
            light = int(self.database.get_sensor_value_by_name(light_switch))
            boost = int(in_sensor_value)
            sensor = "boost"
        self.logger.debug(f"logic logic_fan_boost {humidity} {light} {boost} {sensor}")

        time_now = datetime.now()
        morning = self.database.get_state_by_name("Morning").split(":")
        morning_time = time_now.replace(hour=int(morning[0]), minute=int(morning[1]), second=int(morning[2]))
        evening = self.database.get_state_by_name("Evening").split(":")
        evening_time = time_now.replace(hour=int(evening[0]), minute=int(evening[1]), second=int(evening[2]))

        time_of_day = "night"
        if morning_time <= time_now <= evening_time:
            time_of_day = "day"

        # Logic:
        # If the humidity is too high, clear all timers and fan boost on (if not already)
        # Else if we are on a timer to switch off and not a light switch on, no change
        # Else if light switched on and boost off and during day,
        #   clear all timers and set timed trigger to light switch in <N> minutes
        # Else if light switch off and not on humidity boost,
        #   clear all timers and set timed trigger to switch to light switch in <M> minutes
        # Else if humidity and humidity below limit, switch off

        if self.database.get_sensor_value_by_name(control_relay) == "1":

            # If the humidity is too high, fan boost on (if not already)
            # TODO Add the temperatures to the state table (or as a sensor?)
            if humidity > 60.0:
                self.humidity_boost[humidity_sensor] = 1
                if boost == 0:
                    self.database.delete_once_triggers(boost_relay)
                    self.set_sensor_by_name(boost_relay, V_STATUS, "1")

            # Else if we are on a timer to switch off and not a light switch on, no change
            elif self.database.next_relay_switch_time_value(boost_relay, "0") != {} and \
                    not (sensor == "light" and light == 1):
                pass

            # Else if light switched on and boost off and during day,
            #   clear all timers and set timed trigger to light switch in <N> minutes
            elif sensor == "light" and time_of_day == "day" and boost == 0:
                self.database.delete_once_triggers(boost_relay)
                delayed_datetime = time_now + \
                                   timedelta(minutes=self.database.get_state_by_name("Fan boost startup delay"))
                delayed_time = delayed_datetime.strftime("%H:%M:%S")
                self.database.create_trigger(boost_relay, -1, delayed_time,
                                             light_switch, "Once", "Delayed fan boost")

            # Else if light switch off and not on humidity boost,
            #   clear all timers and set timed trigger to switch to light switch in <M> minutes
            elif sensor == "light" and light == 0 and self.humidity_boost[humidity_sensor] == 0:
                self.database.delete_once_triggers(boost_relay)
                # Switch off the boost after a few minutes
                delayed_datetime = time_now + \
                                   timedelta(minutes=self.database.get_state_by_name("Fan boost stop delay"))
                delayed_time = delayed_datetime.strftime("%H:%M:%S")
                self.database.create_trigger(boost_relay, -1, delayed_time,
                                             "0", "Once",
                                             "Delayed fan off")

            # Else if humidity and humidity below limit, switch off
            # TODO Add the temperatures to the state table (or as a sensor?)
            elif self.humidity_boost[humidity_sensor] == 1 and humidity < 55.0:
                self.humidity_boost[humidity_sensor] = 0
                if boost == 1:
                    self.database.delete_once_triggers(boost_relay)
                    self.set_sensor_by_name(boost_relay, V_STATUS, "0")

        return

    def set_sensor_by_name(self, in_sensor_name, in_variable_type, in_value):
        self.logger.debug(f"logic set_sensor_by_name {in_sensor_name} {in_variable_type} {in_value}")

        sensor_details = self.database.find_sensor_by_name(in_sensor_name)

        if sensor_details is not None:
            return self.message_handler.set_sensor(sensor_details["PublishTopic"],
                                                   sensor_details["MySensorsNodeId"],
                                                   sensor_details["MySensorsSensorId"],
                                                   in_variable_type,
                                                   in_value)

        return 1
