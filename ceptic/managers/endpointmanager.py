from functools import wraps
from ceptic.common import CepticCommands as Commands

def get_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def get_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def post_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def post_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def update_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def update_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def delete_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def delete_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def stream_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def stream_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def streamget_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def streamget_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def streampost_decorator_client(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated

def streampost_decorator_server(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        returned = func(*args, **kwargs)
    return decorated


class EndpointManager(object):
    """
    Used to manage endpoints for CEPtic implementations
    """
    def __init__(self):
        self.commandMap = {}

    @classmethod
    def client(cls):
        spec = cls()
        spec.add_command(Commands.GET, get_decorator_client)
        spec.add_command(Commands.POST, post_decorator_client)
        spec.add_command(Commands.UPDATE, update_decorator_client)
        spec.add_command(Commands.DELETE, delete_decorator_client)
        spec.add_command(Commands.STREAM, stream_decorator_client)
        spec.add_command(Commands.STREAMGET, streamget_decorator_client)
        spec.add_command(Commands.STREAMPOST, streampost_decorator_client)
        return spec

    @classmethod
    def server(cls):
        spec = cls()
        spec.add_command(Commands.GET, get_decorator_server)
        spec.add_command(Commands.POST, post_decorator_server)
        spec.add_command(Commands.UPDATE, update_decorator_server)
        spec.add_command(Commands.DELETE, delete_decorator_server)
        spec.add_command(Commands.STREAM, stream_decorator_server)
        spec.add_command(Commands.STREAMGET, streamget_decorator_server)
        spec.add_command(Commands.STREAMPOST, streampost_decorator_server)
        return spec

    def add_command(self, command, decorator=None):
        self.commandMap.setdefault(command,[decorator,{}])

    def add_endpoint(self, command, endpoint, func):
        """
        Add endpoint to a command
        :param command: string representing command
        :param endpoint: unique string name representing endpoint
        :param func: function to return
        :return: None
        """
        self.commandMap.setdefault(command,[None,{}])[1][endpoint] = func

    def get_endpoint(self, command, endpoint):
        """
        Return the function mapped to endpoint string
        :param command: string
        :param endpoint: string
        :return: function object to be used
        """
        try:
            decorator,endpointMap = self.commandMap[command]
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
            return self.commandMap[command][1].pop(endpoint)
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
        return self.commandMap.pop(command)
