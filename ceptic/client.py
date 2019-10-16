import getopt
import json
import os
import socket
import functools

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticStatusCode,CepticResponse,CepticRequest,CepticCommands
from ceptic.common import create_command_settings,decode_unicode_hook
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,create_ssl_config


def create_client_settings(version="1.0.0", send_cache=409600, headers_max_size=1024000):
    settings = {}
    settings["version"] = str(version)
    settings["send_cache"] = int(send_cache)
    settings["headers_max_size"] = int(headers_max_size)
    settings["default_port"] = 9000
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
    response = CepticResponse.get_with_socket(s,request.settings["maxMsgLength"])
    return response


class CepticClient(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, check_hostname=True, secure=True):
        self.settings = settings
        # set up endpoint manager
        self.endpointManager = EndpointManager.client()
        # set up certificate manager
        ssl_config = create_ssl_config(certfile=certfile,keyfile=keyfile,cafile=cafile,
                                       check_hostname=check_hostname,secure=secure)
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
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add post command
        self.endpointManager.add_command(
            "post",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add update command
        self.endpointManager.add_command(
            "update",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )
        # add delete command
        self.endpointManager.add_command(
            "delete",
            basic_client_command,
            create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000)
            )

    def verify_request(self,command, endpoint, headers):
        # verify command is of proper length and exists in endpoint manager
        if not command:
            raise ValueError("command must be provided")
        if len(command) > 128:
            raise ValueError("command must be less than 128 char long")
        if not self.endpointManager.get_command(command):
            raise ValueError("command '{}' cannot be found in endpoint manager".format(command))
        # verify endpoint is of proper length
        if not endpoint:
            raise ValueError("endpoint must be provided")
        if len(endpoint) > 128:
            raise ValueError("endpoint must be less than 128 char long")
        # verify command, endpoint, headers together are of proper length
        json_headers = json.dumps(headers)
        if len(json_headers) > self.settings["headers_max_size"]:
            raise ValueError("json headers are {} chars too long; max size is {}".format(
                len(conn_request)-self.settings["headers_max_size"],
                self.settings["headers_max_size"]))

    def connect_ip(self, host, port, command, endpoint, headers, body=None):  # connect to ip
        """
        Connect to ceptic server at given ip
        :param ip: string ip:port address, written as XXX.XXX.XXX.XXX:XXXX
        :param data: data to be inserted into json to send to server
        :param endpoint: name of endpoint to perform for client-server
        :param dataToStore: optional data to NOT send to the server but keep for local reference
        :return: depends on data returned by endpoint's function
        """
        # verify args
        try:
            # create Content-Length header if body exists and is not already there
            if body and not headers.get("Content-Length",None):
                headers["Content-Length"] = len(body)
            self.verify_request(command, endpoint, headers)
        except ValueError as e:
            raise e
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(5)
        try:
            s.connect((host, port))
        except Exception as e:
            # TODO: better error handling for server not available and host/port being bad
            s.close()
            return CepticResponse(404, "Server at {} not available".format(ip))
        # create request
        request = CepticRequest(command=command,endpoint=endpoint,headers=headers,body=body)
        return self.connect_protocol_client(s, request)

    def connect_url(self, url, command, headers, body=None):
        try:
            host = None
            port = None
            endpoint = ""
            hostAndPort = None
            hostPortAndEndpoint = url.strip().split("/", 1)
            hostAndPort = hostPortAndEndpoint[0]
            if len(hostPortAndEndpoint) > 1:
                endpoint = hostPortAndEndpoint[1]
            if len(endpoint) == 0:
                endpoint = "/"
            if (":") not in hostAndPort:
                host = hostAndPort
                port = self.settings["default_port"]
            else:
                host,port = hostAndPort.split(":")
                port = int(port)
            return self.connect_ip(host, port, command, endpoint, headers, body)
        except ValueError as e:
            raise e
        except IndexError as e:
            raise e

    def connect_protocol_client(self, s, request):
        """
        Perform general ceptic protocol handshake to continue connection
        :param s: socket instance (socket.socket)
        :param request:
        :return:
        """
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            return CepticResponse(400, str(e))
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # check if command exists; stop connection if not
        try:
            command_func,settings = self.endpointManager.get_command(request.command)
        except KeyError:
            s.close()
            return CepticResponse(499, "client does not recognize command: {}".format(command))
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
