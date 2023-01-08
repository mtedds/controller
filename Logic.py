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
            'Ensuite humidity': self.logic_ensuite_humidity,
            'Ensuite light switch': self.logic_ensuite_light,
        }

    # Find the sensor, check if it has a function and then call it
    def run_sensor_set_logic(self, in_sensor_id, in_sensor_value):
        self.logger.debug(f"logic run_sensor_set_logic {in_sensor_id} {in_sensor_value}")

        sensor = self.database.object_find("Sensor", {"SensorId": in_sensor_id})
        if len(sensor) == 1:
            if sensor[0]["SensorName"] in self.logic_methods:
                self.logic_methods[sensor[0]["SensorName"]](sensor[0]["SensorName"], in_sensor_value)

    def logic_ensuite_humidity(self, in_sensor_name, in_sensor_value):
        self.logger.debug(f"logic logic_ensuite_humidity {in_sensor_name} {in_sensor_value}")

        # If humidity is >60% and Fan Control is on, turn fan on
        # If humidity is <55%, and Fan Control is on, and light switch is off, turn fan off

        if self.database.get_sensor_value_by_name("Ensuite fan control relay") == "1":

            # Check if we are on a time delay
            if self.database.next_relay_switch_time_value("Ensuite fan boost relay", "0") == {}:
                if float(in_sensor_value) > 60.0 and \
                        self.database.get_sensor_value_by_name("Ensuite fan boost relay") == "0":
                    self.set_sensor_by_name("Ensuite fan boost relay", "1")
                    self.fan_boost_relay_last_value = "1"

                if float(in_sensor_value) < 55.0 and \
                        self.database.get_sensor_value_by_name("Ensuite fan boost relay") == "1" and \
                        self.database.get_sensor_value_by_name("Ensuite light switch") == "0":
                    self.set_sensor_by_name("Ensuite fan boost relay", "0")
                    self.fan_boost_relay_last_value = "0"

        return

    def logic_ensuite_light(self, in_sensor_name, in_sensor_value):
        self.logger.debug(f"logic logic_ensuite_light {in_sensor_name} {in_sensor_value}")

        # If daytime and light turned on, turn on fan after 2 minutes
        # If daytime and light turned off, switch back to previous state
        # During the night, switch is ignored and only humidity controls boost

        if self.database.get_sensor_value_by_name("Ensuite fan control relay") == "1":

            # Clear out any existing timed triggers for the fan boost in case switch has been on and off
            # a few times...
            self.database.delete_once_triggers("Ensuite fan boost relay")

            time_now = datetime.now()
            morning = self.database.get_state_by_name("Morning").split(":")
            morning_time = time_now.replace(hour=int(morning[0]), minute=int(morning[1]), second=int(morning[2]))
            evening = self.database.get_state_by_name("Evening").split(":")
            evening_time = time_now.replace(hour=int(evening[0]), minute=int(evening[1]), second=int(evening[2]))

            if morning_time <= time_now <= evening_time:

                if in_sensor_value == "1":
                    # Remember the current state (although this may be altered by the humidity logic
                    # - which is fine)
                    self.fan_boost_relay_last_value = self.database.get_sensor_value_by_name("Ensuite fan boost relay")

                    delayed_datetime = time_now + \
                                       timedelta(minutes=self.database.get_state_by_name("Fan boost startup delay"))
                    delayed_time = delayed_datetime.strftime("%H:%M:%S")
                    self.database.create_trigger("Ensuite fan boost relay", -1, delayed_time,
                                                 "Ensuite light switch", "Once", "Delayed fan boost")
                else:
                    # Switch off the boost after a few minutes
                    delayed_datetime = time_now + \
                                       timedelta(minutes=self.database.get_state_by_name("Fan boost stop delay"))
                    delayed_time = delayed_datetime.strftime("%H:%M:%S")
                    self.database.create_trigger("Ensuite fan boost relay", -1, delayed_time,
                                                 self.fan_boost_relay_last_value, "Once", "Delayed fan off")

        return

    def set_sensor_by_name (self, in_sensor_name, in_value):
        self.logger.debug(f"logic set_sensor_by_name {in_sensor_name} {in_value}")

        sensor_details = self.database.find_sensor_by_name(in_sensor_name)

        if sensor_details is not None:
            return self.message_handler.set_sensor(sensor_details["PublishTopic"],
                                                   sensor_details["MySensorsNodeId"],
                                                   sensor_details["MySensorsSensorId"],
                                                   sensor_details["VariableType"],
                                                   in_value)

        return 1
