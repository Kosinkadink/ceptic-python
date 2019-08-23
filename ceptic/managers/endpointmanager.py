import re
from functools import wraps
from ceptic.common import CepticCommands as Commands

def get_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated


class EndpointManager(object):
    
    def __init__(self):
        self.commandMap = {}

    @staticmethod
    def client():
        return EndpointClientManager()

    @staticmethod
    def server():
        return EndpointServerManager()


class EndpointClientManager(EndpointManager):
"""
    Used to manage endpoints for CEPtic implementations
    """
    def __init__(self):
        EndpointManager.__init__(self)

    def add_command(self, command, func, decorator=None):
        self.commandMap.setdefault(command,[func,decorator])

    def get_command(self, command):
        """
        Return the function mapped to endpoint string
        :param command: string
        :return: function object to be used
        """
        try:
            func,decorator = self.commandMap[command]
            if decorator is None
                return func
            else:
                return decorator(func)
        except KeyError as e:
            return None
        except IndexError as e:
            return None

    def remove_command(self, command):
        """
        Remove command from manager; returns removed endpoint or None if does not exist
        :param command: string
        :return: either removed endpoint or None
        """
        try:
            return self.commandMap.pop(command)
        except KeyError as e:
            return None


class EndpointServerManager(EndpointManager):
"""
    Used to manage endpoints for CEPtic implementations
    """
    def __init__(self):
        EndpointManager.__init__(self)

    def add_command(self, command, func, decorator=None):
        self.commandMap[command] = [{},func,decorator]

    def get_command(self, command):
        try:
            return self.commandMap[command]
        except KeyError as e:
            return None

    def remove_command(self, command):
        """
        Remove command from manager; returns removed endpoint or None if does not exist
        :param command: string
        :return: either removed endpoint or None
        """
        return self.commandMap.pop(command)

    def add_endpoint(self, command, endpoint):
        """
        Add endpoint to a command
        :param command: string representing command
        :param endpoint: unique string name representing endpoint
        :param func: function to return
        :return: None
        """
        if command not in self.commandMap:
            raise EndpointManagerException("command {} not found".format(command))
        # TODO: add regex functions and update endpoint storage
        allowed_regex = '[!-~]+' # any printable ASCII character BUT space
        variable_regex = '<[a-zA-Z0-9]+>' # varied portion of endpoint
        # remove '/' at beginning and end of endpoint
        # replace '\' with '/' in endpoint

        self.commandMap[command][0][endpoint]

    def get_endpoint(self, command, endpoint):
        """
        Return the function mapped to endpoint string
        :param command: string
        :param endpoint: string
        :return: function object to be used
        """
        try:
            # TODO: change to factor in regex and updated endpoint storage
            endpointMap,func,decorator = self.commandMap[command]
            func = endpointMap[endpoint]
            if decorator is None
                return func
            else:
                return decorator(func)
        except KeyError as e:
            return None
        except IndexError as e:
            return None

    def remove_endpoint(self, command, endpoint):
        """
        Remove endpoint from manager; returns removed endpoint or None if does not exist
        :param command: string
        :param endpoint: string
        :return: either removed endpoint or None
        """
        try:
            return self.commandMap[command][0].pop(endpoint)
        except KeyError as e:
            return None
        except IndexError as e:
            return None

class EndpointManagerException(CepticException):
    pass
