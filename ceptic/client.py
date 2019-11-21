import json
import socket
import uuid

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticStatusCode, CepticResponse, CepticRequest, CepticCommands, CepticException
from ceptic.common import create_command_settings, decode_unicode_hook, is_os_windows
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager, CertificateManagerException, create_ssl_config
from ceptic.managers.streammanager import StreamManager, StreamFrameGen, StreamClosedException, StreamException, \
    StreamTotalDataSizeException
from ceptic.compress import CompressGetter, UnknownCompressionException


def create_client_settings(version="1.0.0",
                           headers_min_size=1024000, headers_max_size=1024000,
                           frame_min_size=1024000, frame_max_size=1024000,
                           content_max_size=10240000,
                           stream_min_timeout=1, stream_timeout=5):
    settings = {"version": str(version),
                "headers_min_size": int(headers_min_size),
                "headers_max_size": int(headers_max_size),
                "frame_min_size": int(frame_min_size),
                "frame_max_size": int(frame_max_size),
                "content_max_size": int(content_max_size),
                "stream_min_timeout": int(stream_min_timeout),
                "stream_timeout": int(stream_timeout),
                "default_port": 9000}
    if settings["frame_min_size"] > settings["frame_max_size"]:
        settings["frame_min_size"] = settings["frame_max_size"]
    return settings


def basic_client_command(stream, request):
    # send body if content length header present
    if request.content_length:
        # TODO: Add file transfer functionality
        try:
            stream.sendall(StreamFrameGen(stream).from_data(request.body))
        except StreamClosedException:
            return CepticResponse(400, errors="stream closed while sending body")
        except StreamException as e:
            stream.send_close()
            return CepticResponse(400, errors="StreamException: {}".format(str(e)))
    # get response
    try:
        response_data = stream.get_full_data()
    except StreamClosedException as e:
        return CepticResponse(400, errors=str(e))
    response = CepticResponse.from_data(response_data)
    # if content length header present, receive response body
    if response.content_length:
        # TODO: Add file transfer functionality
        try:
            response.msg = stream.get_full_data(max_length=response.content_length)
        except StreamTotalDataSizeException:
            stream.send_close("body received is greater than reported content_length")
            response = CepticResponse(400, errors="body received is greater than reported content_length; msg ignored")
        except StreamException as e:
            stream.send_close()
            response = CepticResponse(400,
                                      errors="StreamException type ({}) thrown while receiving response msg: {}".format(
                                          type(e),
                                          str(e))
                                      )
    # return response
    return response


class CepticClient(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, check_hostname=True, secure=True):
        self.settings = settings
        self.shouldStop = False
        self.isRunning = False
        # set up endpoint manager
        self.endpointManager = EndpointManager.client()
        # set up certificate manager
        ssl_config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile,
                                       check_hostname=check_hostname, secure=secure)
        self.certificateManager = CertificateManager.client(ssl_config=ssl_config)
        # create StreamManager dictionary
        self.managerDict = {}
        # do initialization
        self.initialize()

    def initialize(self):
        """
        Initialize client configuration and processes
        :return: None
        """
        # set up certificateManager context
        self.certificateManager.generate_context_tls()
        # add get command
        self.endpointManager.add_command(
            "get",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add post command
        self.endpointManager.add_command(
            "post",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add update command
        self.endpointManager.add_command(
            "update",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add delete command
        self.endpointManager.add_command(
            "delete",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )

    def verify_request(self, request):
        # verify command is of proper length and exists in endpoint manager
        if not request.command:
            raise ValueError("command must be provided")
        if len(request.command) > 128:
            raise ValueError("command must be less than 128 char long")
        if not self.endpointManager.get_command(request.command):
            raise ValueError("command '{}' cannot be found in endpoint manager".format(request.command))
        # verify endpoint is of proper length
        if not request.endpoint:
            raise ValueError("endpoint must be provided")
        if len(request.endpoint) > 128:
            raise ValueError("endpoint must be less than 128 char long")
        # verify command, endpoint, headers together are of proper length
        json_headers = json.dumps(request.headers)
        if len(json_headers) > self.settings["headers_max_size"]:
            raise ValueError("json headers are {} chars too long; max size is {}".format(
                len(json_headers) - self.settings["headers_max_size"],
                self.settings["headers_max_size"]))

    @staticmethod
    def setup_headers(headers, body=None):
        # if headers are None, initialize headers as dict
        if not headers:
            headers = {}
        # create Content-Length header if body exists and is not already there
        if body and not headers.get("Content-Length", None):
            headers["Content-Length"] = len(body)
        return headers

    def connect_ip(self, host, port, command, endpoint, headers, body=None, force_new_stream=False):  # connect to ip
        """
        Connect to ceptic server at given ip
        :param host: string of ip address (ipv4)
        :param port: int corresponding to port
        :param command: string command type of request
        :param endpoint: string endpoint value
        :param headers: dict containing headers
        :param body: optional parameter containing body of request
        :param force_new_stream: optional boolean (default False) to guarantee new StreamManager creation
        :return: CepticResponse instance
        """
        # verify args
        try:
            # create request
            request = CepticRequest(command=command, endpoint=endpoint, headers=headers, body=body)
            self.verify_request(request)
        except ValueError as e:
            raise CepticException(e)
        # if a stream manager does not exist for this host/port combo, open one
        name = (host, port)
        if force_new_stream or self.is_manager_full(name):
            name = uuid.uuid4()
        if not self.get_manager(name):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(5)
            # enable socket blocking
            s.setblocking(True)
            try:
                s.connect((host, port))
            except TypeError:
                s.close()
                raise CepticException("host must be string ({}), port must be int ({})".format(host, port))
            except Exception:
                s.close()
                raise CepticException("Server at {}:{} not available".format(host, port))
            try:
                self.create_new_manager(s, name)
            except CepticException as e:
                s.close()
                raise CepticException("Ceptic handshake failed with server: {}".format(str(e)))
        # use existing manager to start new stream
        manager = self.get_manager(name)
        handler = manager.get_handler(manager.create_handler())
        return self.connect_protocol_client(handler, request)

    def connect_url(self, url, command, headers=None, body=None, force_new_stream=False):
        """
        Connect to ceptic server at given url
        :param url: string in format of ip[:port]/endpoint
        :param command: string command type of request
        :param headers: dict containing headers
        :param body: optional parameter containing body of request
        :param force_new_stream: optional boolean (default False) to guarantee new StreamManager creation
        :return: CepticResponse instance
        """
        try:
            host, port, endpoint = self.get_details_from_url(url)
            return self.connect_ip(host, port, command, endpoint, headers, body, force_new_stream)
        except ValueError as e:
            raise e
        except IndexError as e:
            raise e

    def get_details_from_url(self, url):
        endpoint = ""
        host_port_and_endpoint = url.strip().split("/", 1)
        host_and_port = host_port_and_endpoint[0]
        if len(host_port_and_endpoint) > 1:
            endpoint = host_port_and_endpoint[1]
        if len(endpoint) == 0:
            endpoint = "/"
        if ":" not in host_and_port:
            host = host_and_port
            port = self.settings["default_port"]
        else:
            host, port = host_and_port.split(":")
            port = int(port)
        return host, port, endpoint

    def create_new_manager(self, s, name):
        """
        Perform general ceptic protocol handshake to continue connection
        :param s: socket instance (socket.socket)
        :param name: immutable (string or tuple)
        :return: CepticResponse instance
        """
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            s.close()
            raise e
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # send server relevant values
        stream_settings = {}
        # send version
        s.send_raw(format(self.settings["version"], ">16"))
        # send frame_min_size
        s.send_raw(format(self.settings["frame_min_size"], ">16"))
        # send frame_max_size
        s.send_raw(format(self.settings["frame_max_size"], ">16"))
        # send header_min_size
        s.send_raw(format(self.settings["headers_min_size"], ">16"))
        # send header_max_size
        s.send_raw(format(self.settings["headers_max_size"], ">16"))
        # send stream_min_timeout
        s.send_raw(format(self.settings["stream_min_timeout"], ">4"))
        # send stream_timeout
        s.send_raw(format(self.settings["stream_timeout"], ">4"))
        # get response
        response = s.recv_raw(1)
        # if not positive, get additional info and raise exception
        if response != "y":
            error_string = s.recv(1024)
            raise CepticException("client settings not compatible with server settings: {}".format(error_string))
        # otherwise receive decided values
        else:
            server_frame_max_size_str = s.recv_raw(16).strip()
            server_headers_max_size_str = s.recv_raw(16).strip()
            server_stream_timeout_str = s.recv_raw(4).strip()
            handler_max_count_str = s.recv_raw(4).strip()
            try:
                stream_settings["frame_max_size"] = int(server_frame_max_size_str)
                stream_settings["headers_max_size"] = int(server_headers_max_size_str)
                stream_settings["stream_timeout"] = int(server_stream_timeout_str)
                stream_settings["handler_max_count"] = int(handler_max_count_str)
            except ValueError:
                error_msg = "server's received values were not all int, could not proceed: {},{},{},{}".format(
                    server_frame_max_size_str, server_frame_max_size_str, server_stream_timeout_str,
                    handler_max_count_str)
                raise CepticException(error_msg)
            # make sure server's chosen values are valid for client
            if stream_settings["frame_max_size"] > self.settings["frame_max_size"]:
                raise CepticException("server chose frame_max_size ({}) higher than client's ({})".format(
                    stream_settings["frame_max_size"], self.settings["frame_max_size"]))
            if stream_settings["headers_max_size"] > self.settings["headers_max_size"]:
                raise CepticException("server chose headers_max_size ({}) higher than client's ({})".format(
                    stream_settings["headers_max_size"], self.settings["headers_max_size"]))
            if stream_settings["stream_timeout"] > self.settings["stream_timeout"]:
                raise CepticException("server chose stream_timeout ({}) higher than client's ({})".format(
                    stream_settings["stream_timeout"], self.settings["stream_timeout"]))
        # create stream manager
        manager = StreamManager.client(s, name, stream_settings, self.remove_manager)
        self.managerDict[name] = manager
        manager.daemon = True
        manager.start()

    def get_manager(self, name):
        return self.managerDict.get(name)

    def is_manager_full(self, name):
        manager = self.get_manager(name)
        if not manager:
            return False
        return manager.is_handler_limit_reached()

    def connect_protocol_client(self, stream, request):
        """
        Perform general ceptic protocol handshake to continue connection
        :param stream: StreamHandler instance
        :param request:
        :return: CepticResponse instance
        """
        # create frames from request and send
        stream.sendall(request.generate_frames(stream))
        # wait for response
        try:
            response_data = stream.get_full_data()
        except StreamClosedException as e:
            return CepticResponse(400, errors=str(e))
        response = CepticResponse.from_data(response_data)
        # if successful response, continue
        if response.is_success():
            # get command_func and settings for command
            command_func, settings = self.endpointManager.get_command(request.command)
            # set request settings
            request.settings = settings
            # set stream compression, based on request header
            stream.set_compress(request.compress)
            # perform command and get back response
            response = command_func(stream, request)
            return response
        # otherwise return failed response
        else:
            stream.send_close()
            return response

    def stop(self):
        """
        Properly begin to stop client; tells client StreamManagers to stop
        :return: None
        """
        self.shouldStop = True
        self.close_all_managers()

    def is_stopped(self):
        """
        Returns True if client is not running any managers
        """
        return self.shouldStop and not self.isRunning

    def close_all_managers(self):
        keys = list(self.managerDict)
        for key in keys:
            self.managerDict[key].stop()
            self.remove_manager(key)

    def remove_manager(self, name):
        if self.managerDict.get(name):
            self.managerDict.pop(name)
