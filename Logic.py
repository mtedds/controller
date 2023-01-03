from datetime import datetime

# This class is used to handle all sensor logic, eg. when turn radiators on, make sure HC is on


class Logic:

    def __init__(self, in_message_handler, in_database, inLogger):
        self.logger = inLogger
        self.logger.debug(f"message __init__ {in_message_handler}, {in_database}, {inLogger}")

        self.message_handler = in_message_handler
        self.database = in_database

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
        # If humidity is <55%, and Fan Control is on, turn fan off

        if self.database.get_sensor_value_by_name("Ensuite fan control relay") == "1":

            if float(in_sensor_value) > 60.0 and self.database.get_sensor_value_by_name("Ensuite fan boost relay") == "0":
                self.set_sensor_by_name("Ensuite fan boost relay", "1")

            if float(in_sensor_value) < 55.0 and self.database.get_sensor_value_by_name("Ensuite fan boost relay") == "1":
                self.set_sensor_by_name("Ensuite fan boost relay", "0")

        return

    def logic_ensuite_light(self, in_sensor_name, in_sensor_value):
        self.logger.debug(f"logic logic_ensuite_humidity {in_sensor_name} {in_sensor_value}")

        # If daytime and light turned on, turn on fan after 2 minutes
        # If daytime and light turned off, execute the humidity logic

        if self.database.get_sensor_value_by_name("Ensuite fan control relay") == "1":
            time_now = datetime.now()
            morning = self.database.get_state_by_name("Morning").split(":")
            morning_time = time_now.replace(hour=int(morning[0]), minute=int(morning[1]), second=int(morning[2]))
            evening = self.database.get_state_by_name("Evening").split(":")
            evening_time = time_now.replace(hour=int(evening[0]), minute=int(evening[1]), second=int(evening[2]))

            if morning_time <= time_now <= evening_time:
                if in_sensor_value == "1":
                    # TODO: Need to insert a 2 minute delay somehow...
                    # Needs to check not already turned off - just apply the light switch sensor!
                    self.set_sensor_by_name("Ensuite fan control relay", "1")
                else:
                    return self.logic_ensuite_humidity("Ensuite humidity",
                                                       self.database.get_sensor_value_by_name("Ensuite humidity"))

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
