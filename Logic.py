from datetime import datetime
from datetime import timedelta


# This class is used to handle all sensor logic, eg. when turn radiators on, make sure HC is on


class Logic:

    def __init__(self, in_message_handler, in_database, inLogger):
        self.logger = inLogger
        self.logger.debug(f"message __init__ {in_message_handler}, {in_database}, {inLogger}")

        self.message_handler = in_message_handler
        self.database = in_database

        self.fan_boost_relay_last_value = self.database.get_sensor_value_by_name("Ensuite fan boost relay")

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
                self.logic_methods[sensor[0]["SensorName"]][0](sensor[0]["SensorName"], in_sensor_value,
                                                               self.logic_methods[sensor[0]["SensorName"]][1])

    def logic_fan_boost_humidity(self, in_sensor_name, in_sensor_value, in_arguments):
        # Note that arguments are:
        # 1 = Relay that is set on when we are controlling the fan (off = manual)
        # 2 = Relay to set to switch boost on / off
        # 3 = Sensor for light switch on / off
        self.logger.debug(f"logic logic_ensuite_humidity {in_sensor_name} {in_sensor_value} {in_arguments}")

        control_relay = in_arguments[0]
        boost_relay = in_arguments[1]
        light_switch = in_arguments[2]

        # If humidity is >60% and Fan Control is on, turn fan on
        # If humidity is <55%, and Fan Control is on, and light switch is off, turn fan off

        if self.database.get_sensor_value_by_name(control_relay) == "1":

            # Check if we are on a time delay
            if self.database.next_relay_switch_time_value(boost_relay, "0") == {}:
                # TODO Add the temperatures to the state table (or as a sensor?)
                if float(in_sensor_value) > 60.0 and \
                        self.database.get_sensor_value_by_name(boost_relay) == "0":
                    self.set_sensor_by_name(boost_relay, "1")
                    self.fan_boost_relay_last_value = "1"

                if float(in_sensor_value) < 55.0 and \
                        self.database.get_sensor_value_by_name(boost_relay) == "1" and \
                        self.database.get_sensor_value_by_name(light_switch) == "0":
                    self.set_sensor_by_name(boost_relay, "0")
                    self.fan_boost_relay_last_value = "0"

        return

    def logic_fan_boost_light(self, in_sensor_name, in_sensor_value, in_arguments):
        # Note that arguments are:
        # 1 = Relay that is set on when we are controlling the fan (off = manual)
        # 2 = Relay to set to switch boost on / off
        # 3 = Sensor for light switch on / off
        self.logger.debug(f"logic logic_ensuite_light {in_sensor_name} {in_sensor_value} {in_arguments}")

        control_relay = in_arguments[0]
        boost_relay = in_arguments[1]
        light_switch = in_arguments[2]

        # If daytime and light turned on, turn on fan after 2 minutes
        # If daytime and light turned off, switch back to previous state
        # During the night, switch is ignored and only humidity controls boost

        if self.database.get_sensor_value_by_name(control_relay) == "1":

            # Clear out any existing timed triggers for the fan boost in case switch has been on and off
            # a few times...
            self.database.delete_once_triggers(boost_relay)

            time_now = datetime.now()
            morning = self.database.get_state_by_name("Morning").split(":")
            morning_time = time_now.replace(hour=int(morning[0]), minute=int(morning[1]), second=int(morning[2]))
            evening = self.database.get_state_by_name("Evening").split(":")
            evening_time = time_now.replace(hour=int(evening[0]), minute=int(evening[1]), second=int(evening[2]))

            if morning_time <= time_now <= evening_time:

                if in_sensor_value == "1":
                    # Remember the current state (although this may be altered by the humidity logic
                    # - which is fine)
                    self.fan_boost_relay_last_value = self.database.get_sensor_value_by_name(boost_relay)

                    delayed_datetime = time_now + \
                                       timedelta(minutes=self.database.get_state_by_name("Fan boost startup delay"))
                    delayed_time = delayed_datetime.strftime("%H:%M:%S")
                    self.database.create_trigger(boost_relay, -1, delayed_time,
                                                 light_switch, "Once", "Delayed fan boost")
                else:
                    # Switch off the boost after a few minutes
                    delayed_datetime = time_now + \
                                       timedelta(minutes=self.database.get_state_by_name("Fan boost stop delay"))
                    delayed_time = delayed_datetime.strftime("%H:%M:%S")
                    self.database.create_trigger(boost_relay, -1, delayed_time,
                                                 self.fan_boost_relay_last_value, "Once", "Delayed fan off")

        return

    def logic_fan_boost(self, in_sensor_name, in_sensor_value, in_arguments):
        # This function is called for a humidity change or a light switch change

        # Note that arguments are:
        # 1 = Relay that is set on when we are controlling the fan (off = manual)
        # 2 = Relay to set to switch boost on / off
        # 3 = Sensor for light switch on / off
        # 4 = Humidity sensor
        self.logger.debug(f"logic logic_fan_boost {in_sensor_name} {in_sensor_value} {in_arguments}")

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
                    self.set_sensor_by_name(boost_relay, "1")

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
                                             self.fan_boost_relay_last_value, "Once", "Delayed fan off")

            # Else if humidity and humidity below limit, switch off
            # TODO Add the temperatures to the state table (or as a sensor?)
            elif self.humidity_boost[humidity_sensor] == 1 and humidity < 55.0:
                self.humidity_boost[humidity_sensor] = 0
                if boost == 1:
                    self.database.delete_once_triggers(boost_relay)
                    self.set_sensor_by_name(boost_relay, "0")

        return

    def set_sensor_by_name(self, in_sensor_name, in_value):
        self.logger.debug(f"logic set_sensor_by_name {in_sensor_name} {in_value}")

        sensor_details = self.database.find_sensor_by_name(in_sensor_name)

        if sensor_details is not None:
            return self.message_handler.set_sensor(sensor_details["PublishTopic"],
                                                   sensor_details["MySensorsNodeId"],
                                                   sensor_details["MySensorsSensorId"],
                                                   sensor_details["VariableType"],
                                                   in_value)

        return 1
