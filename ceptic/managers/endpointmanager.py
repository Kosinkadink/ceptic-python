import re
from functools import wraps
#from ceptic.common import CepticException
#from ceptic.common import CepticCommands as Commands


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

    def add_command(self, command, command_func, settings):
        self.commandMap[command] = [{},command_func,settings]

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

    def add_endpoint(self, command, endpoint, handler, settings_override=None):
        """
        Add endpoint to a command
        :param command: string representing command OR list/tuple containing multiple string commands
        :param endpoint: unique string name representing endpoint
        :param settings_override: dictionary representing setting values
        :return: None
        """
        # create list of commands to apply endpoint to
        commands = []
        if not isinstance(command,(list,tuple)):
            commands.append(command)
        else:
            commands = command
        # check if commands exist
        for comm in commands:
            if comm not in self.commandMap:
                raise EndpointManagerException("command '{}' not found".format(comm))
        # regex strings
        allowed_regex = '^[a-zA-Z0-9\-\.\<\>_/]+$' # alphanum and -.<>_
        start_slash_regex = '^/{2,}' # 2 or more slashes at start
        end_slash_regex = '/+$' # slashes at end
        middle_slash_regex = '/{2,}' # 2 or more slashes next to each other
        variable_regex = '\<[a-zA-Z_]+[a-zA-Z0-9_]*\>' # varied portion of endpoint
        # non-matching braces, no content between braces, slash between braces, or multiple braces without slash
        bad_braces_regex = '\<[^\>]*\<|\>[^\<]*\>|\<[^\>]+$|^[^\<]+\>|\<\>|\<([^/][^\>]*/[^/][^\>]*)+\>|\>\<'
        braces_regex = '<[^>]*>' # find variables in endpoint
        replacement_regex = '[!-~][^/]+' # printable ASCII characters; not actually executed here
        # check that endpoint is not empty
        if not endpoint:
            raise EndpointManagerException("endpoint definition cannot be empty")
        # check if using allowed characters
        if re.search(allowed_regex,endpoint) is None:
            raise EndpointManagerException("endpoint definition '{}' contains invalid characters".format(endpoint))
        # remove '/' at end of endpoint
        endpoint = re.sub(end_slash_regex,'',endpoint)
        # add '/' at start of endpoint if one's not there
        if not endpoint.startswith('/'):
            endpoint = "/{}".format(endpoint)
        # otherwise replace multiple '/' at start with single
        else:
            endpoint = re.sub(start_slash_regex,'/',endpoint)
        # check if there are multiple slashes in the middle; if so, invalid
        if re.search(middle_slash_regex,endpoint) is not None:
            raise EndpointManagerException("endpoint definition cannot contain consecutive slashes: {}".format(endpoint))
        # check if braces are incorrect
        if re.search(bad_braces_regex,endpoint) is not None:
            raise EndpointManagerException("endpoint definition contains invalid brace placement: {}".format(endpoint))
        # check if variables exist in endpoint, and if so store their names and replace by regex
        variable_names = []
        braces_found = re.findall(braces_regex,endpoint)
        # escape unsafe regex chars in endpoint
        endpoint = re.escape(endpoint)
        if len(braces_found):
            # check if found variable is valid
            for braces in braces_found:
                if re.search(variable_regex,braces) is None:
                    raise EndpointManagerException("variable '{}' for endpoint definition '{}' must start with non-numerics and only contain alphanum and underscores".format(braces,endpoint))
                # if valid variable, check if it has unique name
                if braces[1:-1] in variable_names:
                    raise EndpointManagerException("multiple instances of same variable '{}' in endpoint definition; variable names in an endpoint definition must be unique".format(braces,endpoint))
                # remove surrounding braces when storing
                variable_names.append(braces[1:-1])
            # replace variable in endpoint with regex
            brace_count = 0
            for braces in braces_found:
                safe_braces = re.escape(re.escape(braces))
                # the variable contained in braces '<variable>' acts as the string to substitute;
                # regex statement is put in its place for usage when looking up proper endpoint.
                endpoint = re.sub(safe_braces,"(?P<{}>{})".format(variable_names[brace_count],replacement_regex),endpoint)
                brace_count+=1
        # add regex to make sure beginning and end of string will be included
        endpoint = "^{}$".format(endpoint)
        # store endpoint for each command
        for comm in commands:
            # check if endpoint already exists
            if endpoint in self.commandMap[comm][0]:
                raise EndpointManagerException("endpoint '{}' for command '{}' already exists; endpoints for a command must be unique".format(endpoint,comm))
            # store endpoint as key, [handler, settings_override] as value
            self.commandMap[comm][0][endpoint] = [handler,settings_override]

    def get_endpoint(self, command, endpoint):
        """
        Return the function mapped to endpoint string
        :param command: string
        :param endpoint: string
        :return: function object to be used
        """
        # check if command exists
        if command not in self.commandMap:
            raise EndpointManagerException("command '{}' not found".format(command))
        # regex strings
        allowed_regex = "^[!-~][^\\\\]+$"
        start_slash_regex = '^/{2,}' # 2 or more slashes at start
        end_slash_regex = '/+$' # slashes at end
        middle_slash_regex = '/{2,}' # 2 or more slashes next to each other
        # check that endpoint is not empty
        if not endpoint:
            raise EndpointManagerException("endpoint cannot be empty")
        # check if using allowed characters
        if re.search(allowed_regex,endpoint) is None:
            raise EndpointManagerException("endpoint '{}' contains invalid characters".format(endpoint))
        # remove '/' at end of endpoint
        endpoint = re.sub(end_slash_regex,'',endpoint)
        # add '/' at start of endpoint if one's not there
        if not endpoint.startswith('/'):
            endpoint = "/{}".format(endpoint)
        # otherwise replace multiple '/' at start with single
        else:
            endpoint = re.sub(start_slash_regex,'/',endpoint)
        # check if there are multiple slashes in the middle; if so, invalid
        if re.search(middle_slash_regex,endpoint) is not None:
            raise EndpointManagerException("endpoint definition cannot contain consecutive slashes: {}".format(endpoint))
        # search endpoint dict for matching endpoint
        endpointMap,command_func,settings = self.commandMap[command]
        proper_endpoint_regex = None
        for endpoint_regex in endpointMap:
            if re.search(endpoint_regex,endpoint) is not None:
                proper_endpoint_regex = endpoint_regex
                break
        # if nothing found, endpoint doesn't exist
        if proper_endpoint_regex is None:
            raise EndpointManagerException("endpoint '{}' cannot be found for command '{}'".format(endpoint,command))
        # otherwise get variable names and handler function
        handler,settings_override = endpointMap[proper_endpoint_regex]
        variable_dict = re.match(proper_endpoint_regex,endpoint).groupdict()
        # return command function, endpoint handler, variable_dict, settings, and settings_override
        return command_func,handler,variable_dict,settings,settings_override

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

class EndpointManagerException(Exception):#CepticException):
    pass

if __name__=="__main__":
    manager = EndpointManager.server()
    manager.add_command("get",None,None)
    manager.add_command("post",None,None)
    manager.add_command("update",None,None)
    manager.add_command("delete",None,None)
    manager.add_endpoint(command=["get","update"],endpoint="robots/<robot>/settings/<setting>",handler=None)
    manager.add_endpoint(command=["get","post"],endpoint="robots/<robot>/settings/",handler=None)
    manager.add_endpoint(command=["get","update"],endpoint="robots/<robot>/",handler=None)
    manager.add_endpoint(command="get",endpoint="robots/",handler=None)
    manager.add_endpoint(command="get",endpoint="/",handler=None)
    for key in manager.commandMap:
        endpointDict,func,settings = manager.commandMap[key]
        print("Command: {}, Func: {}".format(key,func))
        for endpoint in endpointDict:
            handler,settings_override = endpointDict[endpoint]
            print("    {}\n        {}\n        {}".format(endpoint,settings_override,handler))
    print("Getting Endpoints")
    print(manager.get_endpoint(command="get",endpoint="/robots/robot1/settings/setting1"))
    print(manager.get_endpoint(command="get",endpoint="/robots/robot1/settings/"))
    print(manager.get_endpoint(command="get",endpoint="/robots/"))
