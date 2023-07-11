import re
from oldceptic.common import CepticException


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

    def add_command(self, command, func, settings):
        self.commandMap[command] = [func, settings]

    def get_command(self, command):
        """
        Return the function mapped to endpoint string
        :param command: string
        :return: function object to be used
        """
        try:
            return self.commandMap[command]
        except KeyError as e:
            raise e

    def remove_command(self, command):
        """
        Remove command from manager; returns removed endpoint or None if does not exist
        :param command: string
        :return: None
        """
        try:
            self.commandMap.pop(command)
        except KeyError:
            return None


class EndpointServerManager(EndpointManager):
    """
    Used to manage endpoints for CEPtic implementations
    """

    def __init__(self):
        EndpointManager.__init__(self)

    def add_command(self, command, command_func, settings):
        self.commandMap[command] = [{}, command_func, settings]

    def get_command(self, command):
        try:
            return self.commandMap[command]
        except KeyError as e:
            raise e

    def remove_command(self, command):
        """
        Remove command from manager; returns removed endpoint or None if does not exist
        :param command: string
        :return: either removed endpoint or None
        """
        try:
            self.commandMap.pop(command)
        except KeyError:
            return None

    def add_endpoint(self, command, endpoint, handler, settings_override=None):
        """
        Add endpoint to a command
        :param command: string representing command OR list/tuple containing multiple string commands
        :param endpoint: unique string name representing endpoint
        :param handler: function corresponding to endpoint behavior
        :param settings_override: dictionary representing setting values
        :return: None
        """
        # create list of commands to apply endpoint to
        commands = []
        if not isinstance(command, (list, tuple)):
            commands.append(command)
        else:
            commands = command
        # check if commands exist
        for comm in commands:
            if comm not in self.commandMap:
                raise EndpointManagerException("command '{}' not found".format(comm))
        # get back endpoint formatted into regex
        endpoint = self.convert_endpoint_into_regex(endpoint)
        # store endpoint for each command
        for comm in commands:
            # check if endpoint already exists
            if endpoint in self.commandMap[comm][0]:
                raise EndpointManagerException(
                    "endpoint '{}' for command '{}' already exists; endpoints for a command must be unique".format(
                        endpoint, comm))
            # store endpoint as key, [stream, settings_override] as value
            self.commandMap[comm][0][endpoint] = [handler, settings_override]

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
        allowed_regex = r'^[!-\[\]-~]+$'
        start_slash_regex = '^/{2,}'  # 2 or more slashes at start
        end_slash_regex = '/+$'  # slashes at end
        middle_slash_regex = '/{2,}'  # 2 or more slashes next to each other
        # check that endpoint is not empty
        if not endpoint:
            raise EndpointManagerException("endpoint cannot be empty")
        # check if using allowed characters
        if re.search(allowed_regex, endpoint) is None:
            raise EndpointManagerException("endpoint '{}' contains invalid characters".format(endpoint))
        # remove '/' at end of endpoint
        endpoint = re.sub(end_slash_regex, '', endpoint)
        # add '/' at start of endpoint if one's not there
        if not endpoint.startswith('/'):
            endpoint = "/{}".format(endpoint)
        # otherwise replace multiple '/' at start with single
        else:
            endpoint = re.sub(start_slash_regex, '/', endpoint)
        # check if there are multiple slashes in the middle; if so, invalid
        if re.search(middle_slash_regex, endpoint) is not None:
            raise EndpointManagerException(
                "endpoint definition cannot contain consecutive slashes: {}".format(endpoint))
        # search endpoint dict for matching endpoint
        endpointMap, command_func, settings = self.commandMap[command]
        proper_endpoint_regex = None
        for endpoint_regex in endpointMap:
            if re.search(endpoint_regex, endpoint) is not None:
                proper_endpoint_regex = endpoint_regex
                break
        # if nothing found, endpoint doesn't exist
        if proper_endpoint_regex is None:
            raise KeyError("endpoint '{}' cannot be found for command '{}'".format(endpoint, command))
        # otherwise get variable names and stream function
        handler, settings_override = endpointMap[proper_endpoint_regex]
        variable_dict = re.match(proper_endpoint_regex, endpoint).groupdict()
        # return command function, endpoint stream, variable_dict, settings, and settings_override
        return command_func, handler, variable_dict, settings, settings_override

    def remove_endpoint(self, command, endpoint):
        """
        Remove endpoint from manager; returns removed endpoint or None if does not exist
        :param command: string
        :param endpoint: string
        :return: either removed endpoint or None
        """
        try:
            self.commandMap[command][0].pop(self.convert_endpoint_into_regex(endpoint))
        except KeyError:
            return None
        except IndexError:
            return None

    @staticmethod
    def convert_endpoint_into_regex(endpoint):
        # regex strings
        allowed_regex = r'^[a-zA-Z0-9\-\.\<\>_/]+$'  # alphanum and -.<>_
        start_slash_regex = '^/{2,}'  # 2 or more slashes at start
        end_slash_regex = '/+$'  # slashes at end
        middle_slash_regex = '/{2,}'  # 2 or more slashes next to each other
        variable_regex = r'\<[a-zA-Z_]+[a-zA-Z0-9_]*\>'  # varied portion of endpoint
        # non-matching braces, no content between braces, slash between braces, multiple braces without slash,
        # or characters between slash and outside of braces
        bad_braces_regex = r'\<[^\>]*\<|\>[^\<]*\>|\<[^\>]+$|^[^\<]+\>|\<\>|\<([^/][^\>]*/[^/][^\>]*)+\>|\>\<|\>[' \
                           r'^/]+|/[^/]+\< '
        braces_regex = '<[^>]*>'  # find variables in endpoint
        replacement_regex = r'[!-\.0-~]+'  # printable ASCII characters aside from /; not actually executed here
        # check that endpoint is not empty
        if not endpoint:
            raise EndpointManagerException("endpoint definition cannot be empty")
        # check if using allowed characters
        if re.search(allowed_regex, endpoint) is None:
            raise EndpointManagerException("endpoint definition '{}' contains invalid characters".format(endpoint))
        # remove '/' at end of endpoint
        endpoint = re.sub(end_slash_regex, '', endpoint)
        # add '/' at start of endpoint if one's not there
        if not endpoint.startswith('/'):
            endpoint = "/{}".format(endpoint)
        # otherwise replace multiple '/' at start with single
        else:
            endpoint = re.sub(start_slash_regex, '/', endpoint)
        # check if there are multiple slashes in the middle; if so, invalid
        if re.search(middle_slash_regex, endpoint) is not None:
            raise EndpointManagerException(
                "endpoint definition cannot contain consecutive slashes: {}".format(endpoint))
        # check if braces are incorrect
        if re.search(bad_braces_regex, endpoint) is not None:
            raise EndpointManagerException("endpoint definition contains invalid brace placement: {}".format(endpoint))
        # check if variables exist in endpoint, and if so store their names and replace by regex
        variable_names = []
        braces_found = re.findall(braces_regex, endpoint)
        # escape unsafe regex chars in endpoint
        endpoint = re.escape(endpoint)
        if len(braces_found):
            # check if found variable is valid
            for braces in braces_found:
                if re.search(variable_regex, braces) is None:
                    raise EndpointManagerException(
                        "variable '{}' for endpoint definition '{}' must start with non-numerics and only contain "
                        "alphanum and underscores".format(
                            braces, endpoint))
                # if valid variable, check if it has unique name
                if braces[1:-1] in variable_names:
                    raise EndpointManagerException(
                        "multiple instances of same variable '{}' in endpoint definition; variable names in an "
                        "endpoint definition must be unique".format(
                            braces, endpoint))
                # remove surrounding braces when storing
                variable_names.append(braces[1:-1])
            # replace variable in endpoint with regex
            brace_count = 0
            for braces in braces_found:
                safe_braces = re.escape(re.escape(braces))
                # the variable contained in braces '<variable>' acts as the string to substitute;
                # regex statement is put in its place for usage when looking up proper endpoint.
                endpoint = re.sub(safe_braces, "(?P<{}>{})".format(variable_names[brace_count], replacement_regex),
                                  endpoint)
                brace_count += 1
        # add regex to make sure beginning and end of string will be included
        endpoint = "^{}$".format(endpoint)
        return endpoint


class EndpointManagerException(CepticException):
    pass
