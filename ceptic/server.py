import getopt
import json
import os
import select
import socket
import threading
import functools

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticAbstraction,CepticSettings,CepticCommands,CepticResponse
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,CertificateConfiguration


class CepticServerSettings(CepticSettings):
    """
    Class used to store server settings. Can be expanded upon by directly adding variables to settings dictionary
    """
    def __init__(self, port=9000, name="template", version="1.0.0", send_cache=409600, location=os.getcwd(), block_on_start=False, use_processes=False, max_parallel_count=1, request_queue_size=10):
        CepticSettings.__init__(self)
        self.settings["port"] = int(port)
        self.settings["name"] = str(name)
        self.settings["version"] = str(version)
        self.settings["send_cache"] = int(send_cache)
        self.settings["location"] = str(location)
        self.settings["block_on_start"] = boolean(block_on_start)
        self.settings["use_processes"] = boolean(use_processes)
        self.settings["max_parallel_count"] = int(max_parallel_count)
        self.settings["request_queue_size"] = int(request_queue_size)


def wrap_server_command(func):
    """
    TODO Decorator for server-side commands
    """
    @functools.wraps(func)
    def decorator_server_command(s,request,endpoint_func,endpoint_dict=None):
        # get body if content length header is present
        if "Content-Length" in request.headers:
            # if content length is longer than set max body length, invalid
            if request.headers["Content-Length"] > request.settings["maxBodyLength"]:
                s.sendall("n")
                # send more info here
                s.close()
                return
            s.sendall("y")
            # receive alloted amount of bytes
            body = s.recv(request.headers["Content-Length"])
            # if content type is raw, set request body to unedited received body
            content_type = request.headers["Content-Type"]
            if request.headers["Content-Type"] == "raw":
                request.body = body
            # else if set to json, try to convert body to json
            else if request.headers["Content-Type"] == "application/json":
                try:
                    request.body = json.loads(body, object_pairs_hook=decode_unicode_hook)
                except ValueError as e:
                    # failed to convert, send failed response
                    s.sendall("n")
                    # send more info here
                    s.close()
                    return
            s.sendall("y")
        # perform command function with appropriate params
        func(s,request,endpoint_func,endpoint_dict)
        # close connection
        s.close()
    return decorator_server_command


class CepticServer(CepticAbstraction):

    def __init__(self, settings, certificate_config=None):
        self.settings = settings
        CepticAbstraction.__init__(self)
        self.shouldExit = False
        # set up endpoints
        self.endpointManager = EndpointManager.server()
        self.add_endpoints()
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
            print(str(e))
            self.shouldExit = True

    def start_server(self):
        if self.settings["block_on_start"]:
            self.run_server()
        else:
            server_thread = threading.Thread(target=self.run_server)
            server_thread.daemon=True
            server_thread.start()

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

    def run_server(self, delay_time=0.1):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :return: None
        """
        print('{} server started - version {} on port {}'.format(
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
            print(str(e))
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
            print(str(e))
        serversocket.close()
        self.exit()

    def handle_new_connection(self, s, addr):
        """
        Handles a particular request, to be executed by another thread of process to not block main server loop
        :param s: basic socket instance
        :param addr: socket address
        :return: None
        """
        print("Got a connection from {}".format(addr))
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            print("CertificateManagerException caught, connection terminated: {}".format(str(e)))
            return
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic(s)
        # receive connection request
        client_request = s.recv(2048)
        conn_req = json.loads(client_request, object_pairs_hook=decode_unicode_hook)
        # determine if good to go
        ready_to_go = True
        endpoint_function = None

        responses = {"status": 200, "msg": "OK"}
        try:
            endpoint_function = self.endpointManager.get_endpoint(conn_req["type"],conn_req["endpoint"])
        except KeyError as e:
            ready_to_go = False
            responses.setdefault("errors", []).append("endpoint of type {} not recognized: {}".format(conn_req["type"],conn_req["endpoint"]))
        finally:
            # if ready to go, send confirmation and continue
            if ready_to_go:
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)
                if conn_req["data"] is None:
                    endpoint_function(s)
                else:
                    endpoint_function(s, conn_req["data"])
            # otherwise send info back
            else:
                responses["status"] = 400
                responses["msg"] = "BAD"
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)

    def route(self, func, endpoint, command, settings_override=None):
        """
        Decorator for adding endpoints to server instance
        """
        @functools.wraps(func)
        def decorator_route(func):
            self.endpointManager.add_endpoint(command, endpoint, func, settings_override)
            return func
        return decorator_route
