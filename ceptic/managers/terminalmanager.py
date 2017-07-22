from endpointmanager import EndpointManager


class TerminalManager(EndpointManager):
    """
    Used to manage terminal commands for CEPtic implementations, imports EndpointManager
    """
    def __init__(self):
        EndpointManager.__init__(self)

    def perform_input(self, inp):
        """
        Parses user input and performs command, if exists
        :param inp: string mapped to function
        :return: return value of mapped function or None
        """
        user_inp = inp.split()
        if not user_inp:
            print("no inp")
        try:
            return self.endpointMap[user_inp[0]](user_inp)
        except KeyError, e:
            print(str(e))
            print("ERROR: terminal command {} is not recognized".format(user_inp[0]))
            return None
