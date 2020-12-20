import logging


from Controller import Controller

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# TODO: This should be configurable
f_handler = logging.TimedRotatingFileHandler("controller.log", when="d", interval=1, backupCount=7)
f_handler.setLevel(logging.DEBUG)
f_format = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)

logger.info("Controller started")

thisController = Controller(logger)

# Never reach here!
logger.info("Controller stopping")
logging.shutdown()

