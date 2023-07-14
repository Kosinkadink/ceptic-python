from enum import Enum, IntEnum
from typing import Union, List


class Constants(object):
    DEFAULT_PORT = 9000
    COMMAND_LENGTH = 128
    ENDPOINT_LENGTH = 128


class CepticException(Exception):
    """
    General Ceptic-related exception class.
    """
    pass


class CepticIOException(CepticException):
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


class CepticHeaders(object):
    def __init__(self, headers: Union[dict, None]) -> None:
        if not headers:
            self.headers = {}
        else:
            self.headers = headers

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
