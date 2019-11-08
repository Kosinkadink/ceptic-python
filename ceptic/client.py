import json
import socket
import uuid

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticStatusCode, CepticResponse, CepticRequest, CepticCommands
from ceptic.common import create_command_settings, decode_unicode_hook
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager, CertificateManagerException, create_ssl_config
from ceptic.managers.streammanager import StreamManager, StreamFrame


def create_client_settings(version="1.0.0", send_cache=409600, headers_max_size=1024000, frame_max_size=10,
                           content_max_size=10240000, stream_timeout=5, handler_timeout=5):
    settings = {"version": str(version),
                "send_cache": int(send_cache),
                "headers_max_size": int(headers_max_size),
                "frame_max_size": int(frame_max_size),
                "content_max_size": int(content_max_size),
                "stream_timeout": int(stream_timeout),
                "handler_timeout": int(handler_timeout),
                "default_port": 9000}
    return settings


def wrap_client_command(func):
    """
    Decorator for server-side commands
    """

    def decorator_client_command(s, request):
        # if Content-Length is a header, expect server to respond with validity of body length
        if "Content-Length" in request.headers:
            valid_length = s.recv(1)
            # if server says length is valid, send body
            if valid_length == "y":
                s.sendall(request.body)
            # otherwise, receive response and close connection
            else:
                response = CepticResponse.get_with_socket(s, 1024)
                s.close()
                return response
        # perform and return from command function
        return func(s, request)

    return decorator_client_command


@wrap_client_command
def basic_client_command(s, request):
    response = CepticResponse.get_with_socket(s, request.settings["maxMsgLength"])
    return response


class CepticClient(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, check_hostname=True, secure=True):
        self.settings = settings
        # set up endpoint manager
        self.endpointManager = EndpointManager.client()
        # set up certificate manager
        ssl_config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile,
                                       check_hostname=check_hostname, secure=secure)
        self.certificateManager = CertificateManager.client(ssl_config=ssl_config)
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

    def connect_ip(self, host, port, command, endpoint, headers, body=None):  # connect to ip
        """
        Connect to ceptic server at given ip
        :param host: string of ip address (ipv4)
        :param port: int corresponding to port
        :param command: string command type of request
        :param endpoint: string endpoint value
        :param headers: dict containing headers
        :param body: optional parameter containing body of request
        :return: CepticResponse instance
        """
        # verify args
        try:
            # create Content-Length header if body exists and is not already there
            if body and not headers.get("Content-Length", None):
                headers["Content-Length"] = len(body)
            # create request
            request = CepticRequest(command=command, endpoint=endpoint, headers=headers, body=body)
            self.verify_request(request)
        except ValueError as e:
            raise e
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(5)
        try:
            s.connect((host, port))
        except Exception as e:
            # TODO: better error handling for server not available and host/port being bad
            s.close()
            return CepticResponse(494, "Server at {}:{} not available".format(host, port))
        return self.connect_protocol_client(s, request)

    def connect_url(self, url, command, headers, body=None):
        """
        Connect to ceptic server at given url
        :param url: string in format of ip[:port]/endpoint
        :param command: string command type of request
        :param headers: dict containing headers
        :param body: optional parameter containing body of request
        :return: CepticResponse instance
        """
        try:
            host, port, endpoint = self.get_details_from_url(url)
            return self.connect_ip(host, port, command, endpoint, headers, body)
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

    def connect_protocol_client(self, s, request):
        """
        Perform general ceptic protocol handshake to continue connection
        :param s: socket instance (socket.socket)
        :param request:
        :return: CepticResponse instance
        """
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            return CepticResponse(498, str(e))
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # check if command exists; stop connection if not
        try:
            command_func, settings = self.endpointManager.get_command(request.command)
        except KeyError:
            s.close()
            return CepticResponse(499, "client does not recognize command: {}".format(request.command))
        # set request settings
        request.settings = settings
        # send command
        s.sendall(request.command)
        # send endpoint
        s.sendall(request.endpoint)
        # send connection request
        json_headers = json.dumps(request.headers)
        s.sendall(json_headers)
        # get response from server
        endpoint_found = s.recv(1)
        # if good response, perform command
        if endpoint_found == "y":
            response = command_func(s, request)
            return response
        # otherwise, receive response, close socket, and return
        else:
            response = CepticResponse.get_with_socket(s, 1024)
            s.close()
            return response


def wrap_client_stream_command(func):
    """
    Decorator for server-side commands
    """

    def decorator_client_command(stream, request):
        # if Content-Length is a header, expect server to respond with validity of body length
        if "Content-Length" in request.headers:
            valid_length = stream.recv(1)
            # if server says length is valid, send body
            if valid_length == "y":
                stream.sendall(request.body)
            # otherwise, receive response and close connection
            else:
                response = CepticResponse.get_with_socket(stream, 1024)
                stream.close()
                return response
        # perform and return from command function
        return func(stream, request)

    return decorator_client_command


@wrap_client_stream_command
def stream_client_command(stream, request):
    response = CepticResponse.get_with_socket(stream, request.settings["maxMsgLength"])
    return response


class CepticClientNew(object):

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
            stream_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add post command
        self.endpointManager.add_command(
            "post",
            stream_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add update command
        self.endpointManager.add_command(
            "update",
            stream_client_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add delete command
        self.endpointManager.add_command(
            "delete",
            stream_client_command,
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
            # setup headers
            headers = self.setup_headers(headers)
            # create request
            request = CepticRequest(command=command, endpoint=endpoint, headers=headers, body=body)
            self.verify_request(request)
        except ValueError as e:
            raise e
        # if a stream manager does not exist for this host/port combo, open one
        if force_new_stream:
            name = uuid.uuid4()
        else:
            name = (host, port)
        if not self.get_manager(name):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(5)
            try:
                s.connect((host, port))
            except Exception as e:
                # TODO: better error handling for server not available and host/port being bad
                print("connect_ip ERROR: {},{}".format(str(e), (host, port)))
                s.close()
                return CepticResponse(494, "Server at {}:{} not available".format(host, port))
            self.create_new_manager(s, name)
        # use existing manager to start new stream
        manager = self.get_manager(name)
        handler = manager.get_handler(manager.create_handler())
        print("going to execute connect_protocol_client")
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
        :param request:
        :return: CepticResponse instance
        """
        # wrap socket with TLS, handshaking happens automatically
        print("create_new_manager")
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            return CepticResponse(498, str(e))
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # create stream manager
        manager = StreamManager.client(s, name, self.settings, self.remove_manager)
        self.managerDict[name] = manager
        manager.daemon = True
        manager.start()

    def get_manager(self, name):
        return self.managerDict.get(name)

    def connect_protocol_client(self, stream, request):
        """
        Perform general ceptic protocol handshake to continue connection
        :param stream: StreamHandler instance
        :param request:
        :return: CepticResponse instance
        """
        # create frames from request
        header_frames = request.generate_frames(stream.stream_id, stream.frame_size)

        # send frames
        for frame in header_frames:
            stream.send(frame)
        # wait for response
        print("connect_protocol_client: waiting for response...")
        response_data = stream.get_full_data()
        # response_frame = stream.get_next_frame()
        print("connect_protocol_client: got response: {}".format(response_data))
        # print("connect_protocol_client: got response: {}".format(response_frame.get_data()))
        # get command_func and settings for command
        command_func, settings = self.endpointManager.get_command(request.command)
        # set request settings
        request.settings = settings

        # check if command exists; stop connection if not
        # try:
        #     command_func, settings = self.endpointManager.get_command(request.command)
        # except KeyError:
        #     stream.close()
        #     return CepticResponse(499, "client does not recognize command: {}".format(request.command))
        # set request settings
        # request.settings = settings
        # get response from server
        ##endpoint_found = s.recv(1)
        # if good response, perform command
        ##if endpoint_found == "y":
        ##    response = command_func(s, request)
        ##    return response
        # otherwise, receive response, close socket, and return
        ##else:
        ##    response = CepticResponse.get_with_socket(s, 1024)
        ##    s.close()
        ##    return response

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
