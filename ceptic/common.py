import json

from abc import ABC
from enum import Enum, IntEnum
from typing import Union, List

from ceptic.stream import StreamHandler


class IRemovableManagers(object):
    pass


class Constants(object):
    DEFAULT_PORT = 9000
    COMMAND_LENGTH = 128
    ENDPOINT_LENGTH = 128


class CepticException(Exception):
    """
    General Ceptic-related exception class.
    """
    pass


class CepticRequestVerifyException(CepticException):
    """
    General Ceptic-related exception class.
    """
    pass


class CommandType(object):
    """
    Contains common command types.
    """
    GET = "get"
    POST = "post"
    UPDATE = "update"
    DELETE = "delete"


class CepticStatusCode(IntEnum):
    """
    Contains common status codes and status checks.
    """
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    EXCHANGE_START = 250
    EXCHANGE_END = 251
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNEXPECTED_END = 460
    MISSING_EXCHANGE = 461
    INTERNAL_SERVER_ERROR = 500

    @staticmethod
    def is_success(status_code: int) -> bool:
        return 200 <= status_code <= 399

    @staticmethod
    def is_error(status_code: int) -> bool:
        return 400 <= status_code <= 699

    @staticmethod
    def is_client_error(status_code: int) -> bool:
        return 400 <= status_code <= 499

    @staticmethod
    def is_server_error(status_code: int) -> bool:
        return 500 <= status_code <= 599


class HeaderType(object):
    CONTENT_LENGTH = "Content-Length"
    CONTENT_TYPE = "Content-Type"
    ENCODING = "Encoding"
    AUTHORIZATION = "Authorization"
    EXCHANGE = "Exchange"
    FILES = "Files"
    ERRORS = "Errors"


class SpreadType(Enum):
    NORMAL = 1
    STANDALONE = 2


class CepticHeaders(ABC):
    def __init__(self, headers: Union[dict, None]) -> None:
        self.headers = headers
        if not self.headers:
            self.headers = {}

    # region Errors
    @property
    def errors(self) -> List:
        return self.headers.get(HeaderType.ERRORS, [])

    @errors.setter
    def errors(self, value: Union[List, None]) -> None:
        self.headers[HeaderType.ERRORS] = value

    # endregion

    # region ContentLength
    @property
    def content_length(self) -> int:
        return self.headers.get(HeaderType.CONTENT_LENGTH, 0)

    @content_length.setter
    def content_length(self, value: int) -> None:
        self.headers[HeaderType.CONTENT_LENGTH] = value

    # endregion

    # region ContentType
    @property
    def content_type(self) -> Union[str, None]:
        return self.headers.get(HeaderType.CONTENT_TYPE)

    @content_type.setter
    def content_type(self, value: Union[str, None]) -> None:
        self.headers[HeaderType.CONTENT_TYPE] = value

    # endregion

    # region Encoding
    @property
    def encoding(self) -> Union[str, None]:
        return self.headers.get(HeaderType.ENCODING)

    @encoding.setter
    def encoding(self, value: Union[str, None]) -> None:
        self.headers[HeaderType.ENCODING] = value

    # endregion

    # region Authorization
    @property
    def authorization(self) -> Union[str, None]:
        return self.headers.get(HeaderType.AUTHORIZATION)

    @authorization.setter
    def authorization(self, value: Union[str, None]) -> None:
        self.headers[HeaderType.AUTHORIZATION] = value

    # endregion

    # region Exchange
    @property
    def exchange(self) -> bool:
        return self.headers.get(HeaderType.EXCHANGE, False)

    @exchange.setter
    def exchange(self, value: Union[bool, None]) -> None:
        self.headers[HeaderType.EXCHANGE] = value

    # endregion

    # region Files
    @property
    def files(self) -> List:
        return self.headers.get(HeaderType.FILES, [])

    @files.setter
    def files(self, value: Union[List, None]) -> None:
        self.headers[HeaderType.FILES] = value
    # endregion


class CepticRequest(CepticHeaders):
    def __init__(self, command: str, url: str, body: bytes = None, headers: dict = None) -> None:
        super().__init__(headers)
        self.command = command
        self.url = url
        self.endpoint = ""
        self.body = body
        self.stream = None
        self.host = ""
        self.port = Constants.DEFAULT_PORT

    @staticmethod
    def create_with_endpoint(command: str, endpoint: str, body: bytes = None, headers: dict = None) -> 'CepticRequest':
        request = CepticRequest(command, "", body, headers)
        request.endpoint = endpoint
        return request

    @property
    def body(self) -> bytearray:
        return self._body

    @body.setter
    def body(self, value: bytes):
        if not value:
            value = bytearray()
        self._body = value
        self.content_length = len(value)

    def verify_and_prepare(self) -> None:
        # check that command isn't empty
        if not self.command:
            raise CepticRequestVerifyException("Command cannot be empty.")
        # check that url isn't empty
        if not self.url:
            raise CepticRequestVerifyException("Url cannot be empty.")
        # don't redo verification is already satisfied
        if self.host and self.endpoint:
            return
        # extract request components from url
        components = self.url.split("/", 2)
        # set endpoint
        if len(components) < 2 or not components[1]:
            self.endpoint = "/"
        else:
            self.endpoint = components[1]
        # extract host and port from first component
        elements = components[0].split(":", 2)
        self.host = elements[0]
        if len(elements) > 1:
            try:
                self.port = int(elements[1])
            except ValueError as e:
                raise CepticRequestVerifyException(f"Port must be an integer, not {elements[1]}.") from e

    def get_data(self) -> bytes:
        return f"{self.command}\r\n{self.endpoint}\r\n{json.dumps(self.headers)}".encode()

    @classmethod
    def from_data(cls, data: bytes) -> 'CepticRequest':
        command, endpoint, json_headers = data.decode().split("\r\n")
        return cls.create_with_endpoint(command, endpoint, headers=json_headers)

    def begin_exchange(self) -> Union[StreamHandler, None]:
        response = CepticResponse(CepticStatusCode.EXCHANGE_START)
        response.exchange = True
        # TODO: fill this out once StreamHandler implementation is more complete
        if not self.exchange:
            pass
        return None


class CepticResponse(CepticHeaders):
    def __init__(self, status: int, body: Union[bytes, None] = None, headers: Union[dict, None] = None,
                 errors: Union[List, None] = None, stream: Union[StreamHandler, None] = None) -> None:
        super().__init__(headers)
        self.status = status
        self.body = body
        self.errors = errors
        self.stream = stream

    @property
    def body(self) -> bytearray:
        return self._body

    @body.setter
    def body(self, value: bytes):
        if not value:
            value = bytearray()
        self._body = value
        self.content_length = len(value)

    def get_data(self) -> bytes:
        return f"{self.status}\r\n{json.dumps(self.headers)}".encode()

    @classmethod
    def from_data(cls, data: bytes) -> 'CepticResponse':
        status, json_headers = data.decode().split("\r\n")
        if json_headers:
            return cls(status, headers=json.loads(json_headers))
        return cls(status)
