#!/usr/bin/python2

import getopt
import json
import os
import select
import socket
import threading

import ceptic.common as common
from ceptic.common import CepticAbstraction
from ceptic.managers.certificatemanager import CertificateManager


def main(argv, template_server, location):
    """
    Wrapper function for starting a ceptic server via terminal
    :param argv: arguments from terminal input
    :param template_server: ceptic server class
    :param location: absolute directory to treat as location
    :return: None
    """
    start_raw_input = True
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
                start_raw_input = False

    # start filling in key word dictionary
    kwargs["start_terminal"] = start_raw_input

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
class CepticServerTemplate(CepticAbstraction):
    # don't change this
    startTime = None
    netPass = None
    __location__ = None
    persistVariablesInDict = dict()
    # change this to default values
    varDict = dict(version='3.0.0', serverport=9999, userport=10999, send_cache=409600,
                   scriptname="template", downloadAddrIp='jedkos.com:9011',
                   downloadAddrLoc='protocols/template.py')

    def __init__(self, location=os.getcwd(), server=varDict["serverport"], user=varDict["userport"], start_terminal=True, name="template", version="1.0.0"):
        # set varDict arguments
        self.varDict["scriptname"] = name
        self.varDict["version"] = version
        if server is not None:
            self.persistVariablesInDict["serverport"] = int(server)
        if user is not None:
            self.persistVariablesInDict["userport"] = int(user)
        CepticAbstraction.__init__(self, location)
        self.__location__ = location
        self.startUser = start_terminal
        self.shouldExit = False
        # set up basic terminal commands
        self.terminalManager.add_command("exit", lambda data: self.exit())
        self.terminalManager.add_command("clear", lambda data: self.clear())
        self.terminalManager.add_command("info", lambda data: self.info())
        self.add_terminal_commands()
        # set up endpoints
        self.endpointManager.add_command("ping", self.ping_endpoint)
        self.add_endpoint_commands()
        # set up certificate manager
        self.certificateManager = CertificateManager(CertificateManager.SERVER, self.fileManager)

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
            self.run_server()
        except Exception, e:
            print(str(e))
            self.shouldExit = True

    def start_user_input(self):
        """
        Start thread to handle user input
        :return: None
        """
        if self.startUser:
            raw_input_thread = threading.Thread(target=self.socket_raw_input, args=(self.varDict["userport"],))
            raw_input_thread.daemon = True
            raw_input_thread.start()
            print("user input thread started - port {}".format(self.varDict["userport"]))

    def socket_raw_input(self, admin_port):
        """
        Connect to user terminal via socket
        :param admin_port: integer of user socket port
        :return: None
        """
        # connect to port
        while True:
            userinp = raw_input()
            tries = 0
            success = False
            error = None
            s = None
            while tries < 5:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect(('localhost', admin_port))
                except Exception, e:
                    error = e
                    tries += 1
                else:
                    success = True
                    break
            if not success:
                raise error
            s.sendall(userinp)
            if userinp == 'exit':
                s.close()
                break

    def initialize(self):
        """
        Initialize server configuration and processes
        :return: None
        """
        # perform all tasks
        self.init_spec()
        # set up config
        self.config()
        self.netPass = self.fileManager.get_netpass()
        self.certificateManager.generate_context_tls()
        # run processes now
        self.run_processes()

    def config(self):
        """
        Read config json to fill in varDict
        :return: None
        """
        # if config file does not exist, create your own
        if not os.path.exists(os.path.join(self.fileManager.get_directory("specificparts"), "config.json")):
            with open(os.path.join(self.fileManager.get_directory("specificparts"), "config.json"), "wb") as json_file:
                json_file.write(json.dumps(self.varDict))
        # otherwise, read in values from config file
        else:
            with open(os.path.join(self.fileManager.get_directory("specificparts"), "config.json"), "rb") as json_file:
                self.varDict = json.load(json_file, object_pairs_hook=common.decode_unicode_hook)
                for key in self.persistVariablesInDict:
                    self.varDict[key] = self.persistVariablesInDict[key]

    def init_spec(self):
        """
        Initialize specific ceptic instance files
        :return: None
        """
        # add specific program parts directory to fileManager
        self.fileManager.add_directory("specificparts", self.varDict["scriptname"], "programparts")
        self.init_spec_extra()

    def init_spec_extra(self):
        """
        Function to overload for more specific initialization
        :return: None
        """
        pass

    def info(self):  # display current configuration
        """
        Prints out info about current configuration
        :return: None
        """
        print("-----------")
        for key in sorted(self.varDict):
            print("{}: {}".format(key, self.varDict[key]))
        print("")

    def exit(self):
        """
        Properly begin to exit server; tells server loop to exit, performs clean_processes()
        :return: None
        """
        self.shouldExit = True
        self.clean_processes()

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

    def run_server(self, delay_time=0.1, repeat_func=None):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :param repeat_func: optional function to repeat
        :return: None
        """
        print('%s server started - version %s on port %s\n' % (
            self.varDict["scriptname"], self.varDict["version"], self.varDict["serverport"]))
        self.netPass = self.fileManager.get_netpass()
        # create a socket object
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketlist = []
        # get local machine name
        host = ""
        port = self.varDict["serverport"]
        userport = self.varDict["userport"]

        userinput = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # bind to the port + admin port
        try:
            serversocket.bind((host, port))
            userinput.bind((host, userport))
        except Exception, e:
            print(str(e))
            self.shouldExit = True

        # queue up to 10 requests
        serversocket.listen(10)
        socketlist.append(serversocket)
        # start admin socket
        userinput.listen(2)
        socketlist.append(userinput)

        while 1 and not self.shouldExit:
            if repeat_func is not None:
                repeat_func()

            ready_to_read, ready_to_write, in_error = select.select(socketlist, [], [], delay_time)

            for sock in ready_to_read:
                # establish a connection
                if sock == userinput:
                    user, addr = userinput.accept()
                    userinp = user.recv(128)
                    self.service_terminal(userinp)
                elif sock == serversocket:
                    s, addr = serversocket.accept()
                    newthread = threading.Thread(target=self.handle_new_connection, args=(s, addr))
                    newthread.daemon = True
                    newthread.start()

        userinput.shutdown(socket.SHUT_RDWR)
        userinput.close()
        serversocket.shutdown(socket.SHUT_RDWR)
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
        s = self.certificateManager.wrap_socket(s)
        # wrap socket with SocketCeptic, to send length of message first
        s = common.SocketCeptic(s)
        # receive connection request
        client_request = s.recv(1024)
        conn_req = json.loads(client_request, object_pairs_hook=common.decode_unicode_hook)
        # determine if good to go
        ready_to_go = True
        command_function = None
        responses = {"status": 200, "msg": "OK"}
        # check netpass
        if conn_req["netpass"] != self.netPass:
            ready_to_go = False
            responses.setdefault("errors", []).append("invalid netpass")
        # check script info
        if conn_req["scriptname"] != self.varDict["scriptname"]:
            ready_to_go = False
            responses.setdefault("errors", []).append("invalid scriptname: {}".format(conn_req["scriptname"]))
        if conn_req["version"] != self.varDict["version"]:
            ready_to_go = False
            responses.setdefault("errors", []).append("invalid version")
        try:
            command_function = self.endpointManager.get_command(conn_req["command"])
        except KeyError, e:
            ready_to_go = False
            responses.setdefault("errors", []).append("command not recognized: %s" % conn_req["command"])
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
                responses["scriptname"] = self.varDict["scriptname"]
                responses["version"] = self.varDict["version"]
                # allow download info to not exist
                responses["downloadAddrIp"] = self.varDict.get("downloadAddrIp", "")
                responses["downloadAddrLoc"] = self.varDict.get("downloadAddrLoc", "")
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)
