class EndpointManager(object):
    """
    Used to manage endpoint commands for CEPtic implementations
    """
    def __init__(self):
        self.endpointTypeMap = {}

    def add_command(self, type_name, command, func):
        """
        Add a command as endpoint
        :param type_name: string representing command type
        :param command: unique string name representing command
        :param func: function to return
        :return: None
        """
        self.endpointTypeMap.setdefault(type_name,{})[command] = func

    def get_command(self, type_name, command):
        """
        Return the function mapped to command string
        :param type_name: string
        :param command: string
        :return: function object to be used
        """
        try:
            func = self.endpointTypeMap[type_name][command]
            return func
        except KeyError as e:
            return None

    def remove_command(self, type_name, command):
        """
        Remove command from manager; returns removed command or None if does not exist
        :param type_name: string
        :param command: string
        :return: either removed command or None
        """
        try:
            return self.endpointTypeMap[type_name].pop(command)
        except KeyError as e:
            return None

    def remove_type(self, type_name):
        """
        Remove type from manager; returns removed command or None if does not exist
        :param type_name: string
        :return: either removed command or None
        """
        return self.endpointTypeMap.pop(type_name)
