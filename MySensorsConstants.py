# These are taken from the MySensors protocol
# and are used in the Controller and Message classes

# Command types from mySensors
COMMAND_PRESENTATION = '0'
COMMAND_SET = '1'
COMMAND_REQ = '2'
COMMAND_INTERNAL = '3'
COMMAND_STREAM = '4'

# Sensor types (also node types) from Presentation
S_ARDUINO_NODE = '17'
S_ARDUINO_REPEATER_NODE = '18'

# Internal message types from mySensors
I_SKETCH_NAME = '11'
I_SKETCH_VERSION = '12'
I_PRESENTATION = '19'
I_DISCOVER_REQUEST = '20'
I_DISCOVER_RESPONSE = '21'

days_of_week = {'Monday': 0,
                'Tuesday': 1,
                'Wednesday': 2,
                'Thursday': 3,
                'Friday': 4,
                'Saturday': 5,
                'Sunday': 6}
