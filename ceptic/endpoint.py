import re
from typing import Union, List, Callable

from ceptic.common import CepticException, Constants
from ceptic.stream import CepticRequest, CepticResponse, StreamFrame

EndpointEntry = Callable[[CepticRequest], CepticResponse]


class ParsedEndpoint(object):
    def __init__(self, endpoint: str, querystring: str, queryparams: dict[str, str]):
        self.endpoint = endpoint
        self.querystring = querystring
        self.queryparams = queryparams


class EndpointManagerException(CepticException):
    """
    Stream-related Ceptic exception.
    """
    pass


class ServerSettings(object):
    def __init__(self,
                 port: int = Constants.DEFAULT_PORT,
                 version: str = "1.0.0",
                 headers_min_size: int = 1024000, headers_max_size: int = 1024000,
                 frame_min_size: int = 1024000, frame_max_size: int = 1024000,
                 body_max: int = 102400000,
                 stream_min_timeout: int = 1, stream_timeout: int = 5,
                 read_buffer_size: int = 102400000, send_buffer_size: int = 102400000,
                 handler_max_count: int = 0,
                 request_queue_size: int = 10,
                 verbose: bool = False,
                 daemon: bool = False):
        self._port = port
        self._version = version
        self._headers_min_size = headers_min_size
        self._headers_max_size = headers_max_size
        self._frame_min_size = frame_min_size if frame_min_size < frame_max_size else frame_max_size
        self._frame_max_size = frame_max_size
        if self._frame_min_size < 1000:
            raise ValueError("frame_min_size must be at least 1000; was {}.".format(self._frame_min_size))
        self._body_max = body_max
        self._stream_min_timeout = stream_min_timeout
        self._stream_timeout = stream_timeout
        if send_buffer_size < frame_max_size + StreamFrame.PREFIX_SIZE or \
                read_buffer_size < frame_max_size + StreamFrame.PREFIX_SIZE:
            raise ValueError("send and read buffer sizes must be greater than "
                             "frame_max_size+{} ({}); were {} and {}.".format(StreamFrame.PREFIX_SIZE,
                                                                              frame_max_size + StreamFrame.PREFIX_SIZE,
                                                                              send_buffer_size, read_buffer_size))
        self._send_buffer_size = send_buffer_size
        self._read_buffer_size = read_buffer_size
        self._handler_max_count = handler_max_count
        self._request_queue_size = request_queue_size
        self._verbose = verbose
        self._daemon = daemon

    @property
    def port(self) -> int:
        return self._port

    @property
    def version(self) -> str:
        return self._version

    @property
    def headers_min_size(self) -> int:
        return self._headers_min_size

    @property
    def headers_max_size(self) -> int:
        return self._headers_max_size

    @property
    def frame_min_size(self) -> int:
        return self._frame_min_size

    @property
    def frame_max_size(self) -> int:
        return self._frame_max_size

    @property
    def body_max(self) -> int:
        return self._body_max

    @property
    def stream_min_timeout(self) -> int:
        return self._stream_min_timeout

    @property
    def stream_timeout(self) -> int:
        return self._stream_timeout

    @property
    def read_buffer_size(self) -> int:
        return self._read_buffer_size

    @property
    def send_buffer_size(self) -> int:
        return self._send_buffer_size

    @property
    def handler_max_count(self) -> int:
        return self._handler_max_count

    @property
    def request_queue_size(self) -> int:
        return self._request_queue_size

    @property
    def verbose(self) -> bool:
        return self._verbose

    @property
    def daemon(self) -> bool:
        return self._daemon


class CommandSettings(object):
    def __init__(self, body_max: int, time_max: int) -> None:
        self.body_max = body_max
        self.time_max = time_max

    def copy(self) -> 'CommandSettings':
        return CommandSettings(self.body_max, self.time_max)

    @staticmethod
    def combine(initial: 'CommandSettings', updates: 'CommandSettings') -> 'CommandSettings':
        body_max = updates.body_max if updates.body_max >= 0 else initial.body_max
        time_max = updates.time_max if updates.time_max >= 0 else initial.time_max
        return CommandSettings(body_max, time_max)

    @staticmethod
    def create_with_body_max(body_max: int) -> 'CommandSettings':
        return CommandSettings(body_max, -1)


class CommandEntry(object):

    allowed_regex = re.compile(r"^[!-\[\]-~]+$")  # ! to [ and ] to ~ ascii characters
    start_slash_regex = re.compile(r"^/{2,}")  # 2 or more slashes at start
    end_slash_regex = re.compile(r"/+$")  # slashes at the end
    middle_slash_regex = re.compile(r"/{2,}")  # 2 or more slashes next to each other

    # alphanumerical and -.<>_/
    allowed_regex_convert = re.compile(r"^[a-zA-Z0-9\-.<>_/]+$")
    # varied portion of endpoint - cannot start with number, only letters and _
    variable_regex = re.compile(r"^[a-zA-Z_]+[a-zA-Z0-9_]*$")
    # non-matching braces, no content between braces, open brace at end, slash between braces,
    # multiple braces without slash, or characters between slash and outside of braces
    bad_braces_regex = re.compile(r"<[^>]*<|>[^<]*>|<[^>]+$|^[^<]+>|<>|<$|<([^/][^>]*/[^/][^>]*)+>|><|>[^/]+|/[^/]+< ")

    braces_regex = re.compile(r"<([^>]*)>")  # find variables in endpoint
    replacement_regex_string = "([!-\\.0-~]+)"

    def __init__(self, command: str, settings: Union[CommandSettings, ServerSettings]) -> None:
        self.command = command
        self.settings = settings if isinstance(settings, CommandSettings)\
            else CommandSettings.create_with_body_max(settings.body_max)
        self.endpoint_map: dict[EndpointPattern, EndpointSaved] = dict()

    def add_endpoint(self, endpoint: str, entry: EndpointEntry, endpoint_settings: CommandSettings = None) -> None:
        # convert endpoint into EndpointPattern
        endpoint_pattern = self.convert_endpoint_into_regex(endpoint)
        # check if endpoint already exists
        if endpoint_pattern in self.endpoint_map:
            raise EndpointManagerException(f"endpoint '{endpoint}' for command '{self.command}' already exists; "
                                           f"endpoints for a command must be unique")
        # set settings for endpoint to use
        settings_to_use = CommandSettings.combine(self.settings, endpoint_settings) if endpoint_settings \
            else self.settings
        # put pattern into endpoint map
        self.endpoint_map[endpoint_pattern] = EndpointSaved(entry, endpoint_pattern.variables, settings_to_use)

    def get_endpoint(self, endpoint: str) -> 'EndpointValue':
        # separate query string from endpoint
        parsed = self.separate_querystring(endpoint)
        endpoint = parsed.endpoint
        # check that endpoint is not empty
        if not endpoint.strip():
            raise EndpointManagerException("endpoint cannot be empty")
        # check if using allowed characters
        if not self.allowed_regex.search(endpoint):
            raise EndpointManagerException(f"endpoint '{endpoint}' contains invalid characters")
        # remove '/' at end of endpoint
        endpoint = re.sub(self.end_slash_regex, "", endpoint, 1)
        # add '/' to start of endpoint if not present
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        # otherwise replace multiple '/' at start with single
        else:
            endpoint = re.sub(self.start_slash_regex, "/", endpoint, 1)
        # check if there are multiple slashes in the middle; if so, invalid
        if self.middle_slash_regex.search(endpoint):
            raise EndpointManagerException(f"endpoint cannot contain consecutive slashes: {endpoint}")
        # search endpoint map for matching endpoint
        match: Union[re.Match, None] = None
        match_endpoint_saved: Union[EndpointSaved, None] = None
        for key in self.endpoint_map.keys():
            match = key.pattern.search(endpoint)
            if match:
                match_endpoint_saved = self.endpoint_map[key]
                break
        # if nothing found, endpoint doesn't exist
        if not match_endpoint_saved:
            raise EndpointManagerException(f"endpoint '{endpoint}' cannot be found for command '{self.command}")
        # get endpoint variable values from match and fill out dict
        values: dict[str, str] = dict()
        index = 1
        for variable_name in match_endpoint_saved.variables:
            values[variable_name] = match.group(index)
            index += 1
        return EndpointValue(match_endpoint_saved.entry, values, parsed.queryparams, parsed.querystring,
                             match_endpoint_saved.settings)

    def remove_endpoint(self, endpoint: str) -> Union['EndpointSaved', None]:
        try:
            return self.endpoint_map.pop(self.convert_endpoint_into_regex(endpoint))
        except (EndpointManagerException, KeyError):
            return None

    def convert_endpoint_into_regex(self, endpoint: str) -> 'EndpointPattern':
        # check that endpoint is not empty
        if not endpoint.strip():
            raise EndpointManagerException("endpoint definition cannot be empty")
        # check if using allowed characters
        if not self.allowed_regex_convert.search(endpoint):
            raise EndpointManagerException(f"endpoint definition '{endpoint}' contains invalid characters")
        # remove '/' at end of endpoint
        endpoint = re.sub(self.end_slash_regex, "", endpoint, count=1)
        # add '/' to start of endpoint if not present
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        # otherwise replace multiple '/' with single
        else:
            endpoint = re.sub(self.start_slash_regex, "/", endpoint, count=1)
        # check if there are multiple slashes in the middle; if so, invalid
        if self.middle_slash_regex.search(endpoint):
            raise EndpointManagerException(f"endpoint definition cannot contain consecutive slashes: {endpoint}")
        # check if braces are incorrect
        if self.bad_braces_regex.search(endpoint):
            raise EndpointManagerException("endpoint definition contains invalid brace placement")
        # check if variables exist in endpoint, and if so store their names and replace by regex
        braces_matcher: list[str] = re.findall(self.braces_regex, endpoint)
        # escape unsafe characters in endpoint
        endpoint = re.escape(endpoint)
        variable_names = []
        for name in braces_matcher:
            # check if found variable is valid
            if not self.variable_regex.search(name):
                raise EndpointManagerException(f"variable '{name}' for endpoint definition '{endpoint}' must start with"
                                               f" non-numerics and only contain alphanum and underscores")
            # check if it has a unique name
            if name in variable_names:
                raise EndpointManagerException(f"multiple instances of variable '{name}' in endpoint definition "
                                               f"'{endpoint}' variable names in an endpoint definition must be unique")
            # store variable name
            variable_names.append(name)
        # replace variables in endpoint with regex
        for variable_name in variable_names:
            # add braces to either side of variable name (escape twice)
            safe_braces = re.escape(re.escape(f"<{variable_name}>"))
            # variable contained in braces '<variable>' acts as the string to substitute;
            # regex statement is put in its place for usage when looking up proper endpoint
            endpoint = re.sub(safe_braces, self.replacement_regex_string, endpoint, 1)
        # add regex to make sure beginning and end of string will be included
        endpoint = f"^{endpoint}$"
        # return pattern generated from endpoint
        return EndpointPattern(re.compile(endpoint), variable_names)

    @staticmethod
    def separate_querystring(raw_endpoint: str) -> ParsedEndpoint:
        split = raw_endpoint.split("?", 1)
        if len(split) == 1:  # if nothing to split, return default values
            return ParsedEndpoint(raw_endpoint, "", dict())
        endpoint, querystring = split[0], split[1]
        queryparams: dict[str, str] = dict()
        # parse query params from query string
        if querystring:
            param_pairs = querystring.split("&")
            for pair in param_pairs:
                var, value = pair.split("=", 1)
                queryparams[var] = value
        return ParsedEndpoint(endpoint, querystring, queryparams)


class EndpointPattern(object):
    def __init__(self, pattern: re.Pattern, variables: Union[List, None]) -> None:
        self.pattern = pattern
        self.variables = variables if variables else []

    def __hash__(self):
        return hash(str(self.pattern))

    def __eq__(self, other: 'EndpointPattern'):
        return self.__class__ == other.__class__ and str(self.pattern) == str(other.pattern)


class EndpointSaved(object):
    def __init__(self, entry: EndpointEntry, variables: list[str], settings: CommandSettings) -> None:
        self.entry = entry
        self.variables = variables
        self.settings = settings


class EndpointValue(object):
    def __init__(self, entry: EndpointEntry, values: dict[str, str], params: dict[str, str], querystring: str,
                 settings: CommandSettings) -> None:
        self.entry = entry
        self.values = values
        self.params = params
        self.querystring = querystring
        self.settings = settings

    def execute(self, request: CepticRequest) -> CepticResponse:
        request.values = self.values
        request.queryparams = self.params
        request.querystring = self.querystring
        return self.entry(request)


class EndpointManager(object):
    def __init__(self, settings: ServerSettings):
        self.server_settings = settings
        self.command_map: dict[str, CommandEntry] = dict()

    def add_command(self, command: str, settings: CommandSettings = None) -> None:
        self.command_map[command] = CommandEntry(command, settings if settings else self.server_settings)

    def get_command(self, command: str) -> CommandEntry:
        return self.command_map.get(command)

    def remove_command(self, command: str) -> Union[CommandEntry, None]:
        return self.command_map.pop(command, None)

    def get_endpoint(self, command: str, endpoint: str) -> EndpointValue:
        command_entry = self.get_command(command)
        if command_entry:
            return command_entry.get_endpoint(endpoint)
        else:
            raise EndpointManagerException(f"command '{command}' not found")

    def add_endpoint(self, command: str, endpoint: str, entry: EndpointEntry, settings: CommandSettings = None) -> None:
        command_entry = self.get_command(command)
        if command_entry:
            command_entry.add_endpoint(endpoint, entry, settings)
        else:
            raise EndpointManagerException(f"command '{command}' not found")

    def remove_endpoint(self, command: str, endpoint: str) -> EndpointSaved:
        command_entry = self.get_command(command)
        return command_entry.remove_endpoint(endpoint) if command_entry else None
