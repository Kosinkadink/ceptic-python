import os
import sys
import json
from sys import version_info
from time import time
# StreamManager import located on bottom of file to allow circular import


def create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000):
    """
    Generates dictionary with command settings
    """
    settings = {"maxMsgLength": int(maxMsgLength),
                "maxBodyLength": int(maxBodyLength)}
    return settings


class CepticCommands(object):
    GET = "get"
    POST = "post"
    UPDATE = "update"
    DELETE = "delete"
    STREAM = "stream"
    STREAMGET = "streamget"
    STREAMPOST = "streampost"


class CepticStatusCode(object):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500

    @staticmethod
    def is_success(status_code):
        return 200 <= status_code <= 299

    @staticmethod
    def is_error(status_code):
        return 400 <= status_code <= 599

    @staticmethod
    def is_client_error(status_code):
        return 400 <= status_code <= 499

    @staticmethod
    def is_server_error(status_code):
        return 500 <= status_code <= 599


class CepticRequest(object):
    def __init__(self, command=None, endpoint=None, headers=None, body=None, settings=None, config_settings=None,
                 url=None):
        self.command = command
        self.endpoint = endpoint
        self.headers = headers
        self.body = body
        self.settings = settings
        self.config_settings = config_settings
        self.url = url
        if not self.headers:
            self.headers = {}
        if self.body:
            if len(self.body) < 500:
                self.content_length = 1000
            else:
                self.content_length = len(body)*2
        self.stream = None
        # TODO: Add properties to easily access common headers (and return None if not present)

    @property
    def content_length(self):
        if self.headers:
            return self.headers.get("Content-Length")
        return None

    @content_length.setter
    def content_length(self, length):
        self.headers["Content-Length"] = length

    @property
    def content_type(self):
        if self.headers:
            return self.headers.get("Content-Type")
        return None

    @content_type.setter
    def content_type(self, value):
        self.headers["Content-Type"] = value

    @property
    def encoding(self):
        if self.headers:
            return self.headers.get("Encoding")
        return None

    @encoding.setter
    def encoding(self, value):
        self.headers["Encoding"] = value

    def generate_frames(self, stream):
        json_headers = json.dumps(self.headers)
        data = "{}\r\n{}\r\n{}".format(self.command, self.endpoint, json_headers)
        generator = StreamFrameGen(stream).from_data(data)
        # make first frame type header
        try:
            frame = next(generator)
        except StopIteration:
            return
        frame.set_to_header()
        yield frame
        for frame in generator:
            yield frame

    @classmethod
    def from_data(cls, data):
        command, endpoint, json_headers = data.split("\r\n")
        headers = json.loads(json_headers, object_pairs_hook=decode_unicode_hook)
        return cls(command, endpoint, headers)


class CepticResponse(object):
    def __init__(self, status, body="", headers=None, errors=None, stream=None):
        self.status = int(status)
        self.headers = headers
        self.body = body
        self.stream = stream
        if not self.headers:
            self.headers = {}
        if self.body:
            if self.body:
                if len(self.body) < 500:
                    self.content_length = 500
                else:
                    self.content_length = len(body) * 2
        if errors:
            self.errors = errors

    @property
    def errors(self):
        if self.headers:
            return self.headers.get("errors")
        return None

    @errors.setter
    def errors(self, errors):
        self.headers["errors"] = errors

    @property
    def content_length(self):
        if self.headers:
            return self.headers.get("Content-Length")
        return None

    @content_length.setter
    def content_length(self, length):
        self.headers["Content-Length"] = length

    @property
    def content_type(self):
        if self.headers:
            return self.headers.get("Content-Type")
        return None

    @content_type.setter
    def content_type(self, value):
        self.headers["Content-Type"] = value

    def is_success(self):
        return CepticStatusCode.is_success(self.status)

    def is_error(self):
        return CepticStatusCode.is_error(self.status)

    def is_client_error(self):
        return CepticStatusCode.is_client_error(self.status)

    def is_server_error(self):
        return CepticStatusCode.is_server_error(self.status)

    def get_dict(self):
        return {"status": self.status, "body": self.body, "headers": self.headers}

    def generate_frames(self, stream):
        data = "{}\r\n{}".format(self.status, json.dumps(self.headers))
        generator = StreamFrameGen(stream).from_data(data)
        for frame in generator:
            yield frame

    @classmethod
    def from_data(cls, data):
        status, json_headers = data.split("\r\n")
        if json_headers:
            return cls(status, headers=json.loads(json_headers, object_pairs_hook=decode_unicode_hook))
        else:
            return cls(status)

    @classmethod
    def from_frame(cls, frame):
        status, json_headers, body = frame.get_data().split("\r\n")
        return cls(status, body, headers=json.loads(json_headers, object_pairs_hook=decode_unicode_hook))

    @staticmethod
    def get_with_socket(s, max_msg_length):
        status = int(s.recv(3))
        body = s.recv(max_msg_length)
        return CepticResponse(status, body)

    def send_with_socket(self, s):
        s.sendall('%3d' % self.status)
        s.sendall(self.body)

    def __repr__(self):
        return str(self.get_dict())

    def __str__(self):
        return self.__repr__()


class CepticException(Exception):
    """
    General Ceptic-related exception class
    """
    pass


class Timer(object):
    __slots__ = ("start_time", "end_time")

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time()

    def update(self):
        self.start()

    def stop(self):
        self.end_time = time()

    def get_time_diff(self):
        return self.end_time - self.start_time

    def get_time(self):
        return time() - self.start_time


def normalize_path(path):
    """
    Changes paths to contain only forward slashes; Windows inter-compatibility fix
    :param path: string path
    :return: forward slash-only path
    """
    if os.name == 'nt':
        path = path.replace('\\', '/')
    return path


def is_os_windows():
    return os.name == 'nt'


def decode_unicode_hook(json_pairs):
    """
    Given json pairs, properly encode strings into utf-8 for general usage
    :param json_pairs: dictionary of json key-value pairs
    :return: new dictionary of json key-value pairs in utf-8
    """
    if version_info >= (3, 0):  # is 3.X
        return dict(json_pairs)
    new_json_pairs = []
    for key, value in json_pairs:
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        if isinstance(key, unicode):
            key = key.encode("utf-8")
        new_json_pairs.append((key, value))
    return dict(new_json_pairs)


from ceptic.managers.streammanager import StreamFrame, StreamFrameGen
from ceptic.encode import EncodeGetter
