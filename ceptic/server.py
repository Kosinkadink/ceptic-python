import json
import select
import socket
import threading
import functools
import copy
import uuid

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticRequest, CepticCommands, CepticResponse, CepticException
from ceptic.common import create_command_settings, decode_unicode_hook
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager, CertificateManagerException, create_ssl_config
from ceptic.managers.streammanager import StreamManager, StreamFrame


def create_server_settings(port=9000, version="1.0.0", send_cache=409600, headers_max_size=1024000,
                           frame_max_size=10, content_max_size=10240000, stream_timeout=5, handler_timeout=5,
                           block_on_start=False, use_processes=False, max_parallel_count=1, request_queue_size=10,
                           verbose=False):
    settings = {"port": int(port),
                "version": str(version),
                "send_cache": int(send_cache),
                "headers_max_size": int(headers_max_size),
                "frame_max_size": int(frame_max_size),
                "content_max_size": int(content_max_size),
                "stream_timeout": int(stream_timeout),
                "handler_timeout": int(handler_timeout),
                "block_on_start": bool(block_on_start),
                "use_processes": bool(use_processes),
                "max_parallel_count": int(max_parallel_count),
                "request_queue_size": int(request_queue_size),
                "verbose": bool(verbose)}
    return settings


def wrap_server_command(func):
    """
    Decorator for server-side commands
    """

    @functools.wraps(func)
    def decorator_server_command(s, request, endpoint_func, endpoint_dict=None):
        # get body if content length header is present
        if "Content-Length" in request.headers:
            # if content length is longer than set max body length, invalid
            if request.headers["Content-Length"] > request.settings["maxBodyLength"]:
                s.sendall("n")
                response = CepticResponse(400, "Content-Length exceeds server's allowed max body length of {}".format(
                    request.settings["maxBodyLength"]))
                response.send_with_socket(s)
                s.close()
                return
            s.sendall("y")
            # receive allotted amount of bytes
            request.body = s.recv(request.headers["Content-Length"])
        # perform command function with appropriate params
        try:
            func(s, request, endpoint_func, endpoint_dict)
        except Exception:
            pass
        # close connection
        s.close()

    return decorator_server_command


@wrap_server_command
def basic_server_command(s, request, endpoint_func, endpoint_dict):
    response = endpoint_func(request, **endpoint_dict)
    if not isinstance(response, CepticResponse):
        try:
            status = int(response[0])
            msg = str(response[1])
            stream = None
            if len(response) == 3:
                stream = response[2]
                # assert isinstance(stream, CepticStream)
            response = CepticResponse(status, msg, stream)
        except Exception:
            error_response = CepticResponse(500,
                                            "endpoint returned invalid data type '{}'' on server".format(
                                                type(response)))
            error_response.send_with_socket(s)
            raise CepticException(
                "expected endpoint_func to return CepticResponse instance, but returned '{}' instead".format(
                    type(response)))
    response.send_with_socket(s)


class CepticServer(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, secure=True):
        self.settings = settings
        self.shouldStop = False
        self.isRunning = False
        # set up endpoint manager
        self.endpointManager = EndpointManager.server()
        # set up certificate manager
        self.certificateManager = CertificateManager.server()
        self.setup_certificate_manager(certfile, keyfile, cafile, secure)
        # initialize
        self.initialize()

    def setup_certificate_manager(self, certfile=None, keyfile=None, cafile=None, secure=True):
        if certfile is None or keyfile is None:
            secure = False
        ssl_config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile, secure=secure)
        self.certificateManager.set_ssl_config(ssl_config)

    def initialize(self):
        """
        Initialize server configuration and processes
        :return: None
        """
        # set up config
        self.certificateManager.generate_context_tls()
        # add get command
        self.endpointManager.add_command(
            "get",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add post command
        self.endpointManager.add_command(
            "post",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add update command
        self.endpointManager.add_command(
            "update",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add delete command
        self.endpointManager.add_command(
            "delete",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )

    def start(self):
        """
        Start running server
        :return: None
        """
        # run processes
        try:
            self.start_server()
        except Exception as e:
            self.stop()
            raise e

    def start_server(self):
        if self.settings["block_on_start"]:
            self.run_server()
        else:
            server_thread = threading.Thread(target=self.run_server)
            server_thread.daemon = True
            server_thread.start()

    def run_server(self, delay_time=0.1):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :return: None
        """
        if self.settings["verbose"]:
            print('ceptic server started - version {} on port {}'.format(
                self.settings["version"], self.settings["port"]))
        # create a socket object
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # serversocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        socketlist = []
        # get local machine name
        host = ""
        port = self.settings["port"]
        # bind to the port
        try:
            serversocket.bind((host, port))
        except Exception as e:
            if self.settings["verbose"]:
                print(str(e))
            self.shouldStop = True

        # queue up to specified number of  requests
        serversocket.listen(self.settings["request_queue_size"])
        socketlist.append(serversocket)
        self.isRunning = True

        while not self.shouldStop:
            ready_to_read, ready_to_write, in_error = select.select(socketlist, [], [], delay_time)

            for sock in ready_to_read:
                # establish a connection
                if sock == serversocket:
                    s, addr = serversocket.accept()
                    # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    newthread = threading.Thread(target=self.handle_new_connection, args=(s, addr))
                    newthread.daemon = True
                    newthread.start()

        try:
            serversocket.shutdown(socket.SHUT_RDWR)
        except IOError as e:
            if self.settings["verbose"]:
                print(str(e))
        serversocket.close()
        self.stop()
        self.isRunning = False

    def handle_new_connection(self, s, addr):
        """
        Handles a particular request, to be executed by another thread of process to not block main server loop
        :param s: basic socket instance
        :param addr: socket address
        :return: None
        """
        if self.settings["verbose"]: print("Got a connection from {}".format(addr))
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            if self.settings["verbose"]: print(
                "CertificateManagerException caught, connection terminated: {}".format(str(e)))
            s.close()
            return
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # receive command
        command = s.recv(128)
        # receive endpoint
        endpoint = s.recv(128)
        # receive headers
        json_headers = s.recv(self.settings["headers_max_size"])
        headers = json.loads(json_headers, object_pairs_hook=decode_unicode_hook)
        # helper vars
        ready_to_go = True
        errors = {}
        # try to get endpoint objects from endpointManager
        try:
            command_func, handler, variable_dict, settings, settings_override = self.endpointManager.get_endpoint(
                command, endpoint)
        except KeyError:
            ready_to_go = False
            errors.setdefault("errors", []).append("endpoint of type {} not recognized: {}".format(command, endpoint))
        # if ready to go, send confirmation and continue
        if ready_to_go:
            s.sendall("y")
            # merge settings
            settings_merged = copy.deepcopy(settings)
            if settings_override is not None:
                settings_merged.update(settings_override)
            # create request object
            request = CepticRequest(command=command, endpoint=endpoint, headers=headers, settings=settings_merged)
            command_func(s, request, handler, variable_dict)
        # otherwise send info back
        else:
            s.sendall("n")
            CepticResponse(400, json.dumps(errors)).send_with_socket(s)

    def route(self, endpoint, command, settings_override=None):
        """
        Decorator for adding endpoints to server instance
        """

        def decorator_route(func):
            self.endpointManager.add_endpoint(command, endpoint, func, settings_override)
            return func

        return decorator_route

    def stop(self):
        """
        Properly begin to stop server; tells server loop to stop, performs clean_processes()
        :return: None
        """
        self.shouldStop = True

    def is_stopped(self):
        """
        Returns True if server is not running
        """
        return self.shouldStop and not self.isRunning


def wrap_server_stream_command(func):
    """
    Decorator for server-side commands
    """

    @functools.wraps(func)
    def decorator_server_command(s, request, endpoint_func, endpoint_dict=None):
        # get body if content length header is present
        if "Content-Length" in request.headers:
            # if content length is longer than set max body length, invalid
            if request.headers["Content-Length"] > request.settings["maxBodyLength"]:
                s.sendall("n")
                response = CepticResponse(400, "Content-Length exceeds server's allowed max body length of {}".format(
                    request.settings["maxBodyLength"]))
                response.send_with_socket(s)
                s.close()
                return
            s.sendall("y")
            # receive alloted amount of bytes
            request.body = s.recv(request.headers["Content-Length"])
        # perform command function with appropriate params
        try:
            func(s, request, endpoint_func, endpoint_dict)
        except Exception:
            pass
        # close connection
        s.close()

    return decorator_server_command


@wrap_server_stream_command
def stream_server_command(s, request, endpoint_func, endpoint_dict):
    response = endpoint_func(request, **endpoint_dict)
    if not isinstance(response, CepticResponse):
        try:
            status = int(response[0])
            msg = str(response[1])
            stream = None
            if len(response) == 3:
                stream = response[2]
                # assert isinstance(stream, CepticStream)
            response = CepticResponse(status, msg, stream)
        except Exception as e:
            error_response = CepticResponse(500,
                                            "endpoint returned invalid data type '{}'' on server".format(
                                                type(response)))
            error_response.send_with_socket(s)
            raise CepticException(
                "expected endpoint_func to return CepticResponse instance, but returned '{}' instead".format(
                    type(response)))
    response.send_with_socket(s)


class CepticServerNew(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, secure=True):
        self.settings = settings
        self.shouldStop = False
        self.isRunning = False
        # set up endpoint manager
        self.endpointManager = EndpointManager.server()
        # set up certificate manager
        self.certificateManager = CertificateManager.server()
        self.setup_certificate_manager(certfile, keyfile, cafile, secure)
        # create StreamManager dict
        self.managerDict = {}
        # initialize
        self.initialize()

    def setup_certificate_manager(self, certfile=None, keyfile=None, cafile=None, secure=True):
        if certfile is None or keyfile is None:
            secure = False
        ssl_config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile, secure=secure)
        self.certificateManager.set_ssl_config(ssl_config)

    def initialize(self):
        """
        Initialize server configuration and processes
        :return: None
        """
        # set up config
        self.certificateManager.generate_context_tls()
        # add get command
        self.endpointManager.add_command(
            "get",
            stream_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add post command
        self.endpointManager.add_command(
            "post",
            stream_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add update command
        self.endpointManager.add_command(
            "update",
            stream_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )
        # add delete command
        self.endpointManager.add_command(
            "delete",
            stream_server_command,
            create_command_settings(maxMsgLength=2048000000, maxBodyLength=2048000000)
        )

    def start(self):
        """
        Start running server
        :return: None
        """
        # run processes
        try:
            self.start_server()
        except Exception as e:
            self.stop()
            raise e

    def start_server(self):
        if self.settings["block_on_start"]:
            self.run_server()
        else:
            server_thread = threading.Thread(target=self.run_server)
            server_thread.daemon = True
            server_thread.start()

    def run_server(self, delay_time=0.1):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :return: None
        """
        if self.settings["verbose"]:
            print('ceptic server started - version {} on port {}'.format(
                self.settings["version"], self.settings["port"]))
        # create a socket object
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # serversocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        socketlist = []
        # get local machine name
        host = ""
        port = self.settings["port"]
        # bind to the port
        try:
            serversocket.bind((host, port))
        except Exception as e:
            if self.settings["verbose"]:
                print("Error while binding serversocket: {}".format(str(e)))
            self.shouldStop = True
        # queue up to specified number of  requests
        serversocket.listen(self.settings["request_queue_size"])
        socketlist.append(serversocket)
        self.isRunning = True

        while not self.shouldStop:
            ready_to_read, ready_to_write, in_error = select.select(socketlist, [], [], delay_time)
            for sock in ready_to_read:
                # establish a connection
                if sock == serversocket:
                    print("about to accept socket")
                    s, addr = serversocket.accept()
                    # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    newthread = threading.Thread(target=self.handle_new_socket, args=(s, addr))
                    newthread.daemon = True
                    newthread.start()
        # shut down managers
        self.close_all_managers()
        # shut down server socket
        try:
            serversocket.shutdown(socket.SHUT_RDWR)
        except IOError as e:
            if self.settings["verbose"]:
                print("Error while shutting down serversocket: {}".format(str(e)))
        serversocket.close()
        self.stop()
        self.isRunning = False

    def handle_new_socket(self, s, addr):
        """
        Handles a particular request, to be executed by another thread of process to not block main server loop
        :param s: basic socket instance
        :param addr: socket address
        :return: None
        """
        print("handle_new_socket")
        if self.settings["verbose"]:
            print("Got a connection from {}".format(addr))
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            if self.settings["verbose"]:
                print("CertificateManagerException caught, connection terminated: {}".format(str(e)))
            s.close()
            return
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # create StreamManager
        manager_uuid = uuid.uuid4()
        manager = StreamManager.server(s, manager_uuid, self.settings, CepticServerNew.handle_new_connection,
                                       self.endpointManager, self.remove_manager)
        self.managerDict[manager_uuid] = manager
        manager.daemon = True
        manager.start()

    @staticmethod
    def handle_new_connection(stream, server_settings, endpoint_manager):
        # get request data from frames
        request_data = stream.get_full_header_data()
        print("SERVER: GOT FULL HEADER DATA: {}".format(request_data))
        # get request from request data
        request = CepticRequest.from_data(request_data)
        # began checking validity of request
        errors = {"errors": list()}
        # check that command and endpoint are of valid length
        if len(request.command) > 128:
            errors["errors"].append(
                "command too long; should be no more than 128 characters, but was {}".format(len(request.command)))
        if len(request.endpoint) > 128:
            errors["errors"].append(
                "endpoint too long; should be no more than 128 characters, but was {}".format(len(request.endpoint)))
        # try to get endpoint objects from endpointManager
        command_func = handler = variable_dict = None
        try:
            command_func, handler, variable_dict, settings, settings_override = endpoint_manager.get_endpoint(
                request.command, request.endpoint)
            # merge settings
            settings_merged = copy.deepcopy(settings)
            if settings_override is not None:
                settings_merged.update(settings_override)
            # set request settings to merged settings
            request.settings = settings_merged
            # set server settings as request's config settings
            request.config_settings = server_settings
        except KeyError as e:
            errors["errors"].append("endpoint of type {} not recognized: {}".format(request.command, request.endpoint))
        # check that Content-Length header (if present) is of allowed length
        if "Content-Length" in request.headers:
            # if content length is longer than set max body length, invalid
            if request.headers["Content-Length"] > request.settings["maxBodyLength"]:
                errors["errors"].append("Content-Length exceeds server's allowed max body length of {}".format(
                    request.settings["maxBodyLength"]))
        # if no errors, continue
        if not len(errors["errors"]):
            command_func(stream, request, handler, variable_dict)
        # otherwise send info back
        else:
            # send frame with error and bad status
            response_frames = CepticResponse(400, json.dumps(errors), headers={"Content-Type": "json"}).generate_frames(
                stream.stream_id, stream.frame_size)
            for frame in response_frames:
                stream.send(frame)
            stream.send_close()

    def route(self, endpoint, command, settings_override=None):
        """
        Decorator for adding endpoints to server instance
        """

        def decorator_route(func):
            self.endpointManager.add_endpoint(command, endpoint, func, settings_override)
            return func

        return decorator_route

    def stop(self):
        """
        Properly begin to stop server; tells server loop to stop, performs clean_processes()
        :return: None
        """
        self.shouldStop = True

    def is_stopped(self):
        """
        Returns True if server is not running
        """
        return self.shouldStop and not self.isRunning

    def close_all_managers(self):
        keys = list(self.managerDict)
        for key in keys:
            self.managerDict[key].stop()
            self.remove_manager(key)

    def remove_manager(self, manager_uuid):
        """
        Removes manager with corresponding UUID from managerDict
        :param manager_uuid: string form of UUID
        :return: None
        """
        if self.managerDict.get(manager_uuid):
            self.managerDict.pop(manager_uuid)
