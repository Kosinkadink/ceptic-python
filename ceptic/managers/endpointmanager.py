class EndpointManager(object):
    """
    Used to manage endpoint commands for CEPtic implementations
    """
    def __init__(self):
        self.endpointMap = {}

    def add_command(self, command, func):
        """
        Add a command as endpoint
        :param command: unique string name
        :param func: function to return
        :return: None
        """
        self.endpointMap[command] = func;

    def get_command(self, command):
        """
        Return the function mapped to command string
        :param command: string
        :return: function object to be used
        """
        if command in self.endpointMap:
            return self.endpointMap[command]
        else:
            return None

    def remove_command(self, command):
        """
        Remove command from manager; returns removed command or None if does not exist
        :param command: string
        :return: either removed command or None
        """
        self.endpointMap.pop(command)

