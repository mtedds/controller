
import sqlite3
from datetime import datetime


# This function is used to convert times (HH:MM:SS) to seconds
def timeConvert(inTime):
    # Commented out as this could impact database performance
    # self.logger.debug(f"database timeConvert {inTime}")
    numbers = inTime.split(":")
    return (int(numbers[0])*60 + int(numbers[1])) * 60 + int(numbers[2])


class Database:
    # TODO: Database name / location needs to be in a constants import
    # to support web2py use of this class (then doesn't need to be an argument here

    def __init__(self, inDatabaseFilename, inLogger):
        self.logger = inLogger
        self.logger.debug(f"database __init__ {inDatabaseFilename}")

        # Set the lock timeout to 5 seconds, which is the default
        self.dbConnection = sqlite3.connect(inDatabaseFilename, timeout=5)
        self.dbConnection.row_factory = sqlite3.Row

        self.dbConnection.create_function("to_seconds", 1, timeConvert)

    def getLastSeconds(self):
        self.logger.debug(f"database getLastSeconds")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Value
                from State
                where Name = "LastSeconds"
                """
                )
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def setLastSeconds(self, inLastSeconds):
        self.logger.debug(f"database setLastSeconds {inLastSeconds}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """Update State
                set Value = ?
                where Name = "LastSeconds"
                """,
                (inLastSeconds,)
                )
        cursor.close()
        self.dbConnection.commit()
        return 0

    def gatewayNames(self):
        self.logger.debug(f"database gatewayNames")
        return [name[0] for name in self.dbConnection.execute("select GatewayName from gateway").fetchall()]

    def gatewayIds(self):
        self.logger.debug(f"database gatewayIds")
        return [name[0] for name in self.dbConnection.execute("select GatewayId from gateway").fetchall()]

    def gatewaySubscribes(self):
        self.logger.debug(f"database gatewaySubscribes")
        return [name[0] for name in self.dbConnection.execute("select SubscribeTopic from gateway").fetchall()]

    def gatewayPublishes(self):
        self.logger.debug(f"database gatewayPublishes")
        return [name[0] for name in self.dbConnection.execute("select PublishTopic from gateway").fetchall()]

    def gatewayFindFromSubscribeTopic(self, inSubscribeTopic):
        self.logger.debug(f"database gatewayFindFromSubscribeTopic {inSubscribeTopic}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select GatewayId, GatewayName,
                BrokerHost, ClientId,
                SubscribeTopic, PublishTopic,
                Username, Password, LastSeen
                from Gateway
                where SubscribeTopic = ?""",
                (inSubscribeTopic,))
        row = cursor.fetchone()
        cursor.close()
        self.logger.debug(f"database gatewayFindFromSubscribeTopic {inSubscribeTopic} = {row}")
        return row

    def nodeFindFromMyNode(self, inGatewayId, inMyNode):
        self.logger.debug(f"database nodeFindFromMyNode {inGatewayId}, {inMyNode}")
        # Should probably do something if find more than one...
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select ifnull(max(nodeid), -1) as NodeId
                from Node
                where GatewayId = ?
                and MySensorsNodeId = ?""",
                (inGatewayId, inMyNode))
        row = cursor.fetchone()
        cursor.close()
        return row["NodeId"]

    def sensorFindFromMySensor(self, inNodeId, inMySensor):
        self.logger.debug(f"database sensorFindFromMySensor {inNodeId}, {inMySensor}")
        # Should probably do something if find more than one...
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select ifnull(max(SensorId), -1)
                from Sensor
                where NodeId = ?
                and MySensorsSensorId = ?""",
                (inNodeId, inMySensor))
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def getNextId(self, inTable):
        self.logger.debug(f"database getNextId {inTable}")
        # Find the next Id for a generic table - start at 1
        cursor = self.dbConnection.cursor()
        sql = "select ifnull(max("+inTable+"id) + 1, 1) from "+inTable
        cursor.execute(sql)
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    # Creates a new node row with the values provided (generates the Id column)
    # Also updates the last seen date time
    def object_create(self, inTable, inValues):
        self.logger.debug(f"database object_create {inTable}, {inValues}")
        sql1 = "insert into " + inTable + " (" + inTable + "Id,"
        sql2 = " values (?,"
        for column in inValues.keys():
            sql1 = sql1 + column + ","
            sql2 = sql2 + "?,"
        sql1 = sql1 + "LastSeen)"
        sql2 = sql2 + "strftime('%s', 'now'))"
        vals = list(inValues.values())
        nextObjectId = self.getNextId(inTable)
        vals.insert(0, nextObjectId)
        cursor = self.dbConnection.cursor()
        cursor.execute(sql1 + sql2, vals)
        self.dbConnection.commit()
        cursor.close()
        return nextObjectId

    # Takes a key field value with a set of updates and applies to the node row
    # Assumes key column name is "Table"Id, eg. NodeId
    # Also updates the last seen date time
    def objectUpdate(self, inTable, inKeyValue, inUpdates):
        self.logger.debug(f"database objectUpdate {inTable}, {inKeyValue}, {inUpdates}")
        sql = "update " + inTable + " set "
        for column in inUpdates.keys():
            sql = sql + column + "=?,"
        sql = sql + "LastSeen = strftime('%s', 'now') "
        sql = sql + "where " + inTable + "id=?"
        vals = list(inUpdates.values())
        vals.append(inKeyValue)
        cursor = self.dbConnection.cursor()
        cursor.execute(sql, vals)
        self.dbConnection.commit()
        cursor.close()
        return 0

    # Check if the node exists and create if not
    # We are only provided the owning Gateway and MySensors Node Id
    def nodeCreateUpdate(self, inGatewayId, inMyNode, inValues):
        self.logger.debug(f"database nodeCreateUpdate {inGatewayId}, {inMyNode}, {inValues}")
        nodeFound = self.nodeFindFromMyNode(inGatewayId, inMyNode)
        if nodeFound >= 0:
            self.objectUpdate("Node", nodeFound, inValues)
        elif nodeFound == -1:
            nodeFound = self.object_create("Node", inValues)
        return nodeFound

    # Check if the sensor exists and create if not
    # We are only provided the owning NodeId and MySensors Sensor Id
    def sensorCreateUpdate(self, inNodeId, inMySensor, inValues):
        self.logger.debug(f"database sensorCreateUpdate {inNodeId}, {inMySensor}, {inValues}")
        sensorFound = self.sensorFindFromMySensor(inNodeId, inMySensor)
        if sensorFound >= 0:
            self.objectUpdate("Sensor", sensorFound, inValues)
            return 1
        elif sensorFound == -1:
            sensorFound = self.object_create("Sensor", inValues)
        return sensorFound

    def find_sensor_by_name(self, inSensorName):
        self.logger.debug(f"database find_sensor_by_name {inSensorName}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select PublishTopic, MySensorsNodeId, MySensorsSensorId, VariableType
                from Gateway, Node, Sensor
                where SensorName = ?
                and Sensor.NodeId = Node.NodeId
                and Node.GatewayId = Gateway.GatewayId""",
                (inSensorName,))
        row = cursor.fetchone()
        cursor.close()
        return row

    def get_sensor_value_by_name(self, in_sensor_name):
        self.logger.debug(f"database get_sensor_value_by_name {in_sensor_name}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select ifnull(CurrentValue, "") as currentvalue
            from Sensor
            where SensorName = ?""",
            (in_sensor_name,))
        row = cursor.fetchone()
        cursor.close()
        return row["currentvalue"]

    def timedActionsFired(self, inStartSeconds, inEndSeconds):
        self.logger.debug(f"database timedActionsFired {inStartSeconds}, {inEndSeconds}")
        cursor = self.dbConnection.cursor()
        cursor.execute(
                """select Action.ActionId, Action.SensorName, Action.VariableType, Action.SetValue
                from TimedTrigger, Action
                where TimedTrigger.ActionId = Action.ActionId
                and to_seconds(Time) between ? and ?
                order by to_seconds(Time), TimedTrigger.TimedTriggerId
                """,
                (inStartSeconds, inEndSeconds))
        actions = cursor.fetchall()
        cursor.close()
        return actions

    def nextTriggerTime(self, inSeconds):
        self.logger.debug(f"database nextTriggerTime {inSeconds}")

        current_day_of_week = datetime.now().weekday()

        cursor = self.dbConnection.cursor()
        # If cannot find anything, return 24 hours (ie max + 1)
        cursor.execute(
                """select ifnull(min(to_seconds(TimedTrigger.Time)), 86400) as Seconds
                from TimedTrigger
                where to_seconds(TimedTrigger.Time) > ?
                and day in (-1, ?)
                and Status = "Active"
                order by to_seconds(TimedTrigger.Time) asc
                """,
                (inSeconds, current_day_of_week))
        seconds = cursor.fetchone()
        cursor.close()
        return seconds["Seconds"]

    def hp_is_on(self, in_sensor):
        self.logger.debug(f"database hp_is_on {in_sensor}")

        interval = self.current_relay_interval(in_sensor)

        if interval[0]["SetValue"] == "0":
            return False
        else:
            return True

    # This finds the timed trigger entry for the sensor
    def current_relay_interval(self, in_sensor_name):
        self.logger.debug(f"database current_relay_interval {in_sensor_name}")

        now = datetime.now()
        # Monday is zero in both cases
        current_day_of_week = now.weekday()
        current_time = now.hour * 60 + now.minute

        cursor = self.dbConnection.cursor()
        cursor.execute(
            f"""select SetValue
            , case Day when -1 then {current_day_of_week} else Day end Day
            , Time
            from Action, TimedTrigger
            where SensorName = ?
            and TimedTrigger.ActionId = Action.ActionId
            order by Day, to_seconds(Time)""",
            (in_sensor_name,))
        trigger_times = cursor.fetchall()
        cursor.close()

        # Prime the previous trigger just in case we are early on Monday morning
        return_triggers = {0: trigger_times[len(trigger_times)-1]}

        # Search for today
        for trigger in trigger_times:
            if trigger["Day"] == current_day_of_week:
                if current_time < int(trigger["Time"][0:2]) * 60 + int(trigger["Time"][3:5]):
                    return_triggers[1] = trigger
                    return return_triggers
            elif trigger["Day"] == current_day_of_week + 1:
                # Moved on to tomorrow
                return_triggers[1] = trigger
                return return_triggers
            # Move on...
            return_triggers[0] = trigger

        # Must be end of Sunday
        return_triggers[1] = trigger_times[0]
        return return_triggers

    def next_relay_switch_time(self, in_sensor_name):
        self.logger.debug(f"database current_relay_interval {in_sensor_name}")

        return self.current_relay_interval(in_sensor_name)[1]["Time"]

    def read_prog(self, in_sensor_name):
        self.logger.debug(f"database read_prog {in_sensor_name}")

        cursor = self.dbConnection.cursor()
        # Note that 7 is used as Daily
        cursor.execute(
            f"""select SetValue
                    , case Day when -1 then 7 else Day end Day
                    , Time
                    from Action, TimedTrigger
                    where SensorName = ?
                    and TimedTrigger.ActionId = Action.ActionId
                    order by Day, to_seconds(Time)""",
            (in_sensor_name,))
        trigger_times = cursor.fetchall()
        cursor.close()

        return_triggers = {}
        day = -1

        for trigger in trigger_times:
            if int(trigger["Day"]) > day:
                day = int(trigger["Day"])
                return_triggers[day] = {}
                interval_count = 0

            return_triggers[day][interval_count] = {"Time": trigger["Time"], "SetValue": trigger["SetValue"]}
            interval_count += 1

        return return_triggers

    def get_prog_actionids(self, in_sensor):
        self.logger.debug(f"database get_prog_actionids {in_sensor}")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select Action.ActionId
                    from Action
                    where Sensorname = ?
                    order by SetValue
                    """,
            (in_sensor, ))
        actions = cursor.fetchall()
        cursor.close()

        return {0: actions[0]["actionid"], 1: actions[1]["actionid"]}

    def clear_old_timed_triggers(self, in_sensor, in_actionids):
        self.logger.debug(f"database clear_old_timed_triggers {in_sensor} {in_actionids}")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """delete from TimedTrigger
                    where ActionId in (?, ?)
                    """,
            (in_actionids[0], in_actionids[1]))
        cursor.close()

    def store_prog(self, in_sensor, in_intervals):
        self.logger.debug(f"database store_prog {in_sensor} {in_intervals}")

        days_of_the_week = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

        actions = self.get_prog_actionids(in_sensor)
        self.clear_old_timed_triggers(in_sensor, actions)

        values = {"Status": "External"}

        for day in range(7):
            values["Day"] = day
            for interval in in_intervals[day].keys():
                trigger_desc = f"{in_sensor} Prog {days_of_the_week[day]} {interval} "

                if in_intervals[day][interval][0] != "32:00":
                    values["Description"] = trigger_desc + "on"
                    values["Time"] = in_intervals[day][interval][0] + ":00"
                    values["ActionId"] = actions[1]
                    self.object_create("TimedTrigger", values)

                    values["Description"] = trigger_desc + "off"
                    values["Time"] = in_intervals[day][interval][1] + ":00"
                    values["ActionId"] = actions[0]
                    self.object_create("TimedTrigger", values)

    def read_all_sensors(self):
        self.logger.debug(f"database read_all_sensors")

        cursor = self.dbConnection.cursor()
        cursor.execute(
            """select SensorName, CurrentValue
                    from Sensor
                    """)
        sensor_values = cursor.fetchall()
        cursor.close()

        sensor_dict = {}
        for sensor in sensor_values:
            sensor_dict[sensor["SensorName"]] = sensor["CurrentValue"]

        return sensor_dict
