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
    def __init__(self, command=None, endpoint=None, headers=None, body=None, settings=None, config_settings=None):
        self.command = command
        self.endpoint = endpoint
        self.headers = headers
        self.body = body
        self.settings = settings
        self.config_settings = config_settings
        # TODO: Add properties to easily access common headers (and return None if not present)

    def create_frame(self, stream_id):
        data = "{}\r\n{}\r\n{}".format(self.command, self.endpoint, json.dumps(self.headers))
        return StreamFrame.create_header(stream_id, data)

    def generate_frames(self, stream_id, frame_size):
        data = "{}\r\n{}\r\n{}".format(self.command, self.endpoint, json.dumps(self.headers))
        generator = StreamFrameGen(stream_id, frame_size).from_data(data)
        # make first frame type header
        frame = next(generator)
        frame.set_to_header()
        yield frame
        for frame in generator:
            yield frame

    @classmethod
    def from_data(cls, data):
        command, endpoint, json_headers = data.split("\r\n")
        return cls(command, endpoint, json.loads(json_headers, object_pairs_hook=decode_unicode_hook))


class CepticResponse(object):
    def __init__(self, status, msg, headers=None, stream=None):
        self.status = int(status)
        self.headers = headers
        self.msg = msg
        self.stream = stream

    def get_dict(self):
        return {"status": self.status, "msg": self.msg}

    def create_frame(self, stream_id):
        data = "{}\r\n{}\r\n{}".format(self.status, self.headers, self.msg)
        return StreamFrame.create_header(stream_id, data)

    def generate_frames(self, stream_id, frame_size):
        data = "{}\r\n{}\r\n{}".format(self.status, self.headers, self.msg)
        generator = StreamFrameGen(stream_id, frame_size).from_data(data)
        for frame in generator:
            yield frame

    @classmethod
    def get_from_frame(cls, frame):
        status, json_headers, msg = frame.get_data().split("\r\n")
        return cls(status, msg, headers=json.loads(json_headers, object_pairs_hook=decode_unicode_hook))

    @staticmethod
    def get_with_socket(s, max_msg_length):
        status = int(s.recv(3))
        msg = s.recv(max_msg_length)
        return CepticResponse(status, msg)

    def send_with_socket(self, s):
        s.sendall('%3d' % self.status)
        s.sendall(self.msg)

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
