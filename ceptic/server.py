import getopt
import json
import os
import select
import socket
import threading

from sys import version_info
import ceptic.common as common
from ceptic.common import CepticAbstraction, CepticSettings
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,CertificateConfiguration


class CepticServerSettings(CepticSettings):
    """
    Class used to store server settings. Can be expanded upon by directly adding variables to varDict dictionary
    """
    def __init__(self, port, name="template", version="1.0.0", send_cache=409600, location=os.getcwd(), start_terminal=False, admin_port=-1, block_on_start=False, use_processes=False, max_parallel_count=1, request_queue_size=10):
        CepticSettings.__init__(self)
        self.settings["port"] = int(port)
        self.settings["name"] = str(name)
        self.settings["version"] = str(version)
        self.settings["send_cache"] = int(send_cache)
        self.settings["location"] = str(location)
        self.settings["start_terminal"] = boolean(start_terminal)
        self.settings["admin_port"] = int(admin_port)
        self.settings["block_on_start"] = boolean(block_on_start)
        self.settings["use_processes"] = boolean(use_processes)
        self.settings["max_parallel_count"] = int(max_parallel_count)
        self.settings["request_queue_size"] = int(request_queue_size) 


def main(argv, template_server, location):
    """
    Wrapper function for starting a ceptic server via terminal
    :param argv: arguments from terminal input
    :param template_server: ceptic server class
    :param location: absolute directory to treat as location
    :return: None
    """
    start_input = True
    server_port_string = None
    user_port_string = None
    error_occurred = False
    kwargs = {"location": location}
    try:
        opts, args = getopt.getopt(argv, 'tp:u:', ['port=', 'userport='])
    except getopt.GetoptError:
        print('-p [port] or --port=[port], -u [port] or --userport=[port]')
        quit()
    else:
        for opt, arg in opts:
            if opt in ("-p", "--port"):
                server_port_string = arg
            elif opt in ("-u", "--userport"):
                user_port_string = arg
            elif opt in ("-t",):
                start_input = False

    # start filling in key word dictionary
    kwargs["start_terminal"] = start_input

    if server_port_string is not None:
        try:
            server_port_int = int(server_port_string)
        except ValueError:
            print('ERROR: server port must be an integer')
            error_occurred = True
        else:
            kwargs["server"] = server_port_int
    if user_port_string is not None:
        try:
            user_port_int = int(user_port_string)
        except ValueError:
            print('ERROR: user port must be an integer')
            error_occurred = True
        else:
            kwargs["user"] = user_port_int

    if not error_occurred:
        template_server(**kwargs).start()


# sort of an abstract class; will not work on its own
class CepticServer(CepticAbstraction):

    def __init__(self, settings, certificate_config=None):
        self.settings = settings
        CepticAbstraction.__init__(self)
        self.startUser = start_terminal
        self.blockOnStart = block_on_start
        self.shouldExit = False
        # set up basic terminal commands
        self.terminalManager.add_command("exit", lambda data: self.exit())
        self.terminalManager.add_command("clear", lambda data: self.clear())
        self.terminalManager.add_command("info", lambda data: self.info())
        self.add_terminal_commands()
        # set up endpoints
        self.endpointManager.add_command("singlet", "ping", self.ping_endpoint)
        self.add_endpoint_commands()
        # set up certificate manager
        self.certificateManager = CertificateManager(CertificateManager.SERVER, config=certificate_config)

    def start(self):
        """
        Start running server
        :return: None
        """
        self.run()

    def run(self):
        """
        Begin initialization of server
        :return:
        """
        self.initialize()

    def run_processes(self):
        """
        Attempts to start user input thread and start the server loop
        :return: None
        """
        try:
            self.start_user_input()
            self.start_server()
        except Exception as e:
            print(str(e))
            self.shouldExit = True

    def start_user_input(self):
        """
        Start thread to handle user input
        :return: None
        """
        if self.startUser:
            input_thread = threading.Thread(target=self.socket_input, args=(self.settings["userport"],))
            input_thread.daemon = True
            input_thread.start()
            print("user input thread started - port {}".format(self.settings["userport"]))

    def start_server(self):
        if self.blockOnStart:
            self.run_server()
        else:
            server_thread = threading.Thread(target=self.run_server)
            server_thread.daemon=True
            server_thread.start()

    def initialize(self):
        """
        Initialize server configuration and processes
        :return: None
        """
        # set up config
        self.certificateManager.generate_context_tls()
        # initialize custom behavior
        self.initialize_custom()
        # run processes
        self.run_processes()

    def initialize_custom(self):
        """
        Override function to start custom behavior
        """
        pass

    def info(self):  # display current configuration
        """
        Prints out info about current configuration
        :return: None
        """
        print("-----------")
        for key in sorted(self.settings):
            print("{}: {}".format(key, self.settings[key]))
        print("")

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

    def ping_endpoint(self, s, data=None):
        """
        Simple endpoint, returns PONG to client
        :param s: SocketCeptic instance
        :param data: additional data
        :return: success state
        """
        s.sendall("pong")
        return {"status": 200, "msg": "ping"}

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
        # start admin socket

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
        print("Got a connection from %s" % str(addr))
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            print("CertificateManagerException caught, connection terminated: {}".format(str(e)))
            return
        # wrap socket with SocketCeptic, to send length of message first
        s = common.SocketCeptic(s)
        # receive connection request
        client_request = s.recv(2048)
        conn_req = json.loads(client_request, object_pairs_hook=common.decode_unicode_hook)
        # determine if good to go
        ready_to_go = True
        command_function = None

        responses = {"status": 200, "msg": "OK"}
        try:
            command_function = self.endpointManager.get_command(conn_req["type"],conn_req["command"])
        except KeyError as e:
            ready_to_go = False
            responses.setdefault("errors", []).append("command of type {} not recognized: {}".format(conn_req["type"],conn_req["command"]))
        finally:
            # if ready to go, send confirmation and continue
            if ready_to_go:
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)
                if conn_req["data"] is None:
                    command_function(s)
                else:
                    command_function(s, conn_req["data"])
            # otherwise send info back
            else:
                responses["status"] = 400
                responses["msg"] = "BAD"
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)
