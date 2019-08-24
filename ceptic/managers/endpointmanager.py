import re
from functools import wraps
from ceptic.common import CepticException
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

    def add_command(self, command, func):
        self.commandMap.setdefault(command,func)

    def get_command(self, command):
        """
        Return the function mapped to endpoint string
        :param command: string
        :return: function object to be used
        """
        try:
            func = self.commandMap[command]
            return func
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

    def add_command(self, command, func):
        self.commandMap[command] = [{},func]

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
        :return: None
        """
        if command not in self.commandMap:
            raise EndpointManagerException("command {} not found".format(command))
        # regex strings
        allowed_regex = '^[a-zA-Z0-9\-\.\<\>_/]+$' # a
        start_end_slash_regex = '^/+|/+$'
        middle_slash_regex = '/{2,}' # 2 or more slashes next to each other
        variable_regex = '\<[a-zA-Z_]+[a-zA-Z0-9_]*\>' # varied portion of endpoint
        # non-matching braces, no content between braces, slash between braces, or multiple braces without slash
        bad_braces_regex = '\<[^\>]*\<|\>[^\<]*\>|\<[^\>]+$|^[^\<]+\>|\<\>|\<([^/][^\>]*/[^/][^\>]*)+\>|\>\<'
        braces_regex = '<[^>]*>' # find variables in endpoint
        replacement_regex = '[!-~]+' # printable ASCII characters; not actually executed here
        # check if using allowed characters
        if re.search(allowed_regex,endpoint) is None:
            raise EndpointManagerException("endpoint definition '{}' contains invalid characters".format(endpoint))
        # remove '/' at beginning and end of endpoint
        endpoint = re.sub(start_end_slash_regex,'',endpoint)
        # check if there are multiple slashes in the middle; if so, invalid
        if re.search(middle_slash_regex,endpoint) is not None:
            raise EndpointManagerException("endpoint definition cannot contain consecutive slashes: {}".format(endpoint))
        # check if braces are incorrect
        if re.search(bad_braces_regex,endpoint) is not None:
            raise EndpointManagerException("endpoint definition contains invalid brace placement: {}".format(endpoint))
        # check if variables exist in endpoint, and if so store their names and replace by regex
        variables_found = []
        braces_found = re.findall(braces_regex,endpoint)
        print("braces_found:{}".format(braces_found))
        if len(braces_found):
            # check if found variable is valid
            for braces in braces_found:
                print("braces:{}".format(braces))
                if re.search(variable_regex,braces) is None:
                    raise EndpointManagerException("variable {} for endpoint definition {} must start with non-numerics and only contain alphanum and underscores".format(braces,endpoint))
                # if valid variable, check if it has unique name
                if braces[1:-1] in variables_found:
                    raise EndpointManagerException("multiple instances of same variable {} in endpoint definition; variable names in an endpoint definition must be unique".format(braces,endpoint))
                # remove surrounding braces when storing
                variables_found.append(braces[1:-1])
            # escape unsafe regex chars in endpoint
            endpoint = re.escape(endpoint)
            # replace variable in endpoint with regex
            for braces in braces_found:
                safe_braces = re.escape(braces)
                print("safe_braces:{}".format(safe_braces))
                # the variable contained in braces '<variable>' acts as the string to substitute;
                # regex statement is put in its place for usage when looking up proper endpoint.
                endpoint = re.sub(re.escape(safe_braces),replacement_regex,endpoint)
            # add regex to make sure beginning and end of string will be included
            endpoint = "^{}$".format(endpoint)
        # store endpoint as key, variables as the value
        self.commandMap[command][0][endpoint] = variables_found

    def get_endpoint(self, command, endpoint):
        """
        Return the function mapped to endpoint string
        :param command: string
        :param endpoint: string
        :return: function object to be used
        """
        try:
            # TODO: change to factor in regex and updated endpoint storage
            endpointMap,func = self.commandMap[command]
            func = endpointMap[endpoint]
            return func
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

#if __name__=="__main__":
#    manager = EndpointManager.server()
#    manager.add_command("test",None)
#    manager.add_endpoint(command="test",endpoint="robots/<robot>/settings/<setting>")
#    print(manager.commandMap)
