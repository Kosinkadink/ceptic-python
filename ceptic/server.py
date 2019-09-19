import getopt
import json
import os
import select
import socket
import threading
import functools
import copy

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticRequest,CepticCommands,CepticResponse,CepticException
from ceptic.common import create_command_settings,decode_unicode_hook
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,CertificateConfiguration


def create_server_settings(port=9000, name="template", version="1.0.0", send_cache=409600, headers_max_size=1024000, block_on_start=False, use_processes=False, max_parallel_count=1, request_queue_size=10, verbose=False):
    settings = {}
    settings["port"] = int(port)
    settings["name"] = str(name)
    settings["version"] = str(version)
    settings["send_cache"] = int(send_cache)
    settings["headers_max_size"] = int(headers_max_size)
    settings["block_on_start"] = bool(block_on_start)
    settings["use_processes"] = bool(use_processes)
    settings["max_parallel_count"] = int(max_parallel_count)
    settings["request_queue_size"] = int(request_queue_size)
    settings["verbose"] = bool(verbose)
    return settings


def wrap_server_command(func):
    """
    Decorator for server-side commands
    """
    @functools.wraps(func)
    def decorator_server_command(s,request,endpoint_func,endpoint_dict=None):
        # get body if content length header is present
        if "Content-Length" in request.headers:
            # if content length is longer than set max body length, invalid
            if request.headers["Content-Length"] > request.settings["maxBodyLength"]:
                s.sendall("n")
                response = CepticResponse(400,"Content-Length exceeds server's allowed max body length of {}".format(request.settings["maxBodyLength"]))
                response.send_with_socket(s)
                s.close()
                return
            s.sendall("y")
            # receive alloted amount of bytes
            body = s.recv(request.headers["Content-Length"])
        # perform command function with appropriate params
        try:
            func(s,request,endpoint_func,endpoint_dict)
        except Exception as e:
            pass
        # close connection
        s.close()
    return decorator_server_command


@wrap_server_command
def basic_server_command(s, request, endpoint_func, endpoint_dict):
    response = endpoint_func(request,**endpoint_dict)
    if not isinstance(response,CepticResponse):
        errorResponse = CepticResponse(500,"endpoint returned invalid data type '{}'' on server".format(type(response)))
        errorResponse.send_with_socket(s)
        raise CepticException("expected endpoint_func to return CepticResponse instance, but returned '{}' instead".format(type(response)))
    response.send_with_socket(s)


class CepticServer(object):

    def __init__(self, settings, certificate_config=None):
        self.settings = settings
        self.shouldExit = False
        # set up endpoint manager
        self.endpointManager = EndpointManager.server()
        # set up certificate manager
        self.certificateManager = CertificateManager.server(config=certificate_config)
        # initialize
        self.initialize()

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
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add post command
        self.endpointManager.add_command(
            "get",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add update command
        self.endpointManager.add_command(
            "get",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add delete command
        self.endpointManager.add_command(
            "get",
            basic_server_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )

    def start(self):
        """
        Start running server
        :return: None
        """
        # run processes
        self.run_processes()

    def run_processes(self):
        """
        Attempts to start the server loop
        :return: None
        """
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
            server_thread.daemon=True
            server_thread.start()

    def run_server(self, delay_time=0.1):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :return: None
        """
        if self.settings["verbose"]: print('{} server started - version {} on port {}'.format(
            self.settings["scriptname"], self.settings["version"], self.settings["serverport"]))
        # create a socket object
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #serversocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        socketlist = []
        # get local machine name
        host = ""
        port = self.settings["port"]
        # bind to the port
        try:
            serversocket.bind((host, port))
        except Exception as e:
            if self.settings["verbose"]: print(str(e))
            self.shouldExit = True

        # queue up to 10 requests
        serversocket.listen(self.settings["request_queue_size"])
        socketlist.append(serversocket)

        while not self.shouldExit:
            ready_to_read, ready_to_write, in_error = select.select(socketlist, [], [], delay_time)

            for sock in ready_to_read:
                # establish a connection
                if sock == serversocket:
                    s, addr = serversocket.accept()
                    #s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    newthread = threading.Thread(target=self.handle_new_connection, args=(s, addr))
                    newthread.daemon = True
                    newthread.start()

        try:
            serversocket.shutdown(socket.SHUT_RDWR)
        except IOError as e:
            if self.settings["verbose"]: print(str(e))
        serversocket.close()
        self.stop()

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
            if self.settings["verbose"]: print("CertificateManagerException caught, connection terminated: {}".format(str(e)))
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
            command_func,handler,variable_dict,settings,settings_override = self.endpointManager.get_endpoint(command,endpoint)
        except KeyError as e:
            ready_to_go = False
            responses.setdefault("errors", []).append("endpoint of type {} not recognized: {}".format(command,endpoint))
        # if ready to go, send confirmation and continue
        if ready_to_go:
            s.sendall("y")
            # merge settings
            settings_merged = copy.deepcopy(settings)
            if settings_override is not None:
                settings_merged.update(settings_override)
            # create request object
            request = CepticRequest(command=command,endpoint=endpoint,headers=headers,settings=None)
            command_func(s,request,handler,variable_dict)
        # otherwise send info back
        else:
            s.sendall("n")
            CepticResponse(400,json.dumps(errors)).send_with_socket(s)

    def route(self, func, endpoint, command, settings_override=None):
        """
        Decorator for adding endpoints to server instance
        """
        @functools.wraps(func)
        def decorator_route(func):
            self.endpointManager.add_endpoint(command, endpoint, func, settings_override)
            return func
        return decorator_route

    def exit(self):
        """
        Properly begin to exit server; tells server loop to exit, performs clean_processes()
        :return: None
        """
        self.shouldExit = True
        self.clean_processes()

    def stop(self):
        """
        Alias for exit() function
        """
        self.exit()

    def clean_processes(self):
        """
        Function to overload to perform cleaning before exit
        :return: None
        """
        pass
