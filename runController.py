import time, logging
from datetime import datetime, timedelta
import configparser
import sys
import paho.mqtt.client as mqtt
import sqlite3

from Controller import Controller

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
f_handler = logging.FileHandler("controller.log")
f_handler.setLevel(logging.DEBUG)
f_format = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)

logger.info("Controller started")

thisController = Controller(logger)

# Never reach here!
logger.info("Controller stopping")
logging.shutdown()

