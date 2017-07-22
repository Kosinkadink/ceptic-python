import logging
import logging.handlers
import sys


class LoggerManager(object):
    """
    Used for CEPtic instance logging
    """
    def __init__(self, location, name=None):
        self.logger_dict = {}
        self.__location__ = location
        if name is not None:
            pass

    def create_logger(self, name, filename, level=logging.DEBUG):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        self.logger_dict[name] = logger
        self.add_default_handler_to(name, filename)

    def remove_logger(self, name):
        self.logger_dict.pop(name)

    def add_default_handler_to(self, name, filename):
        # file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename, maxBytes=20000, backupCount=5)
        stream_handler = logging.StreamHandler(sys.stdout)
        file_handler.setFormatter(self.get_basic_format())
        stream_handler.setFormatter(self.get_basic_format())
        self.logger_dict[name].addHandler(file_handler)
        self.logger_dict[name].addHandler(stream_handler)

    @staticmethod
    def get_basic_format():
        formatter = logging.Formatter("%(name)-10s %(levelname)-10s %(asctime)s %(message)s")
        return formatter

