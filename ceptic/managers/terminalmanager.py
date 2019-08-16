from ceptic.common import CepticException


class TerminalManager(object):
    """
    Used to manage terminal commands for CEPtic implementations, imports EndpointManager
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
        return self.endpointMap[command]

    def remove_command(self, command):
        """
        Remove command from manager; returns removed command or None if does not exist
        :param command: string
        :return: either removed command or None
        """
        self.endpointMap.pop(command)

    def perform_input(self, inp):
        """
        Parses user input and performs command, if exists
        :param inp: string mapped to function
        :return: return value of mapped function or None
        """
        user_inp = inp.split()
        if not user_inp:
            print("no input given")
        if user_inp[0] not in self.endpointMap:
            raise TerminalManagerException("ERROR: terminal command {} is not recognized".format(user_inp[0]))
        return self.endpointMap[user_inp[0]](user_inp)


class TerminalManagerException(CepticException):
    pass
