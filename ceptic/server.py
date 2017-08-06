#!/usr/bin/python2

import getopt
import json
import os
import select
import socket
import threading
from time import sleep

import ceptic.common as common
from ceptic.common import CepticAbstraction
from ceptic.managers.certificatemanager import CertificateManager


def main(argv, templateServer, location):
    startRawInput = True
    portS = None
    try:
        opts, args = getopt.getopt(argv, 'tp:', ['port='])
    except getopt.GetoptError:
        print('-p [port] or --port [port] only')
        quit()
    else:
        for opt, arg in opts:
            if opt in ("-p", "--port"):
                portS = arg
            if opt in ("-t",):
                startRawInput = False

    if portS is None:
        templateServer(location, startUser=startRawInput).start()
    else:
        try:
            portI = int(portS)
        except ValueError:
            print('port must be an integer')
        else:
            templateServer(location, serve=portI, startUser=startRawInput).start()


# sort of an abstract class; will not work on its own
class CepticServerTemplate(CepticAbstraction):
    # don't change this
    startTime = None
    netPass = None
    __location__ = None
    # change this to default values
    varDict = dict(version='3.0.0', serverport=9999, userport=10999, send_cache=409600,
                   scriptname="template", downloadAddrIP='jedkos.com:9011',
                   downloadAddrLoc='protocols/template.py')

    def __init__(self, location, serve=varDict["serverport"], user=varDict["userport"], startUser=True):
        self.varDict["serverport"] = int(serve)
        self.varDict["userport"] = int(user)
        CepticAbstraction.__init__(self, location)
        self.__location__ = location
        self.startUser = startUser
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
        self.run()

    def run(self):
        self.initialize()

    def run_processes(self):
        try:
            self.start_user_input()
            self.servergen()
        except Exception, e:
            print(str(e))
            self.shouldExit = True

    def start_user_input(self):
        if self.startUser:
            raw_input_thread = threading.Thread(target=self.socket_raw_input, args=(self.varDict["userport"],))
            raw_input_thread.daemon = True
            raw_input_thread.start()
            print("user input thread started - port {}".format(self.varDict["userport"]))

    def socket_raw_input(self, admin_port):
        # connect to port
        while True:
            userinp = raw_input()
            tries = 0
            success = False
            error = None
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
        # perform all tasks
        self.init_spec()
        # set up config
        self.config()
        self.netPass = self.fileManager.get_netpass()
        self.certificateManager.generateContextTLS()
        # run processes now
        self.run_processes()

    def config(self):
        # if config file does not exist, create your own
        if not os.path.exists(os.path.join(self.fileManager.get_directory("specificparts"), "config.json")):
            with open(os.path.join(self.fileManager.get_directory("specificparts"), "config.json"), "wb") as json_file:
                json_file.write(json.dumps(self.varDict))
        # otherwise, read in values from config file
        else:
            with open(os.path.join(self.fileManager.get_directory("specificparts"), "config.json"), "rb") as json_file:
                string_json = json_file.read()
                self.varDict = json.loads(string_json, object_pairs_hook=common.decode_unicode_hook)

    def init_spec(self):
        # add specific program parts directory to fileManager
        self.fileManager.add_directory("specificparts", self.varDict["scriptname"], "programparts")
        self.init_spec_extra()

    def init_spec_extra(self):
        pass

    def info(self):  # display current configuration
        """
        Prints out info about current configuration
        :return: 
        """
        print("-----------")
        for key in sorted(self.varDict):
            print("{}: {}".format(key, self.varDict[key]))
        print("")

    def exit(self):
        self.shouldExit = True
        self.cleanProcesses()

    def ping_endpoint(self, s, data=None):
        """
        Simple endpoint, returns PONG to client
        :param s: SocketCeptic instance
        :param data: additional data
        :return: success state
        """
        s.sendall("pong")
        return {"status": 200, "msg": "ping"}

    def cleanProcesses(self):
        pass

    def servergen(self, repeatFunc=None):
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
            if repeatFunc is not None:
                repeatFunc()
            sleep(.1)

            ready_to_read, ready_to_write, in_error = select.select(socketlist, [], [], 0)

            for sock in ready_to_read:
                # establish a connection
                if sock == userinput:
                    user, addr = userinput.accept()
                    userinp = user.recv(128)
                    self.service_terminal(userinp)
                elif sock == serversocket:
                    s, addr = serversocket.accept()
                    newthread = threading.Thread(target=self.handleNewConnection, args=(s, addr))
                    newthread.daemon = True
                    newthread.start()

        userinput.shutdown(socket.SHUT_RDWR)
        userinput.close()
        serversocket.shutdown(socket.SHUT_RDWR)
        serversocket.close()
        self.exit()

    def handleNewConnection(self, s, addr):
        print("Got a connection from %s" % str(addr))
        # wrap socket with TLS, handshaking happens automatically
        s = self.certificateManager.wrap_socket(s)
        # wrap socket with SocketCeptic, to send length of message first
        s = common.SocketCeptic(s)
        # receive connection request
        client_request = s.recv(1024)
        conn_req = json.loads(client_request, object_pairs_hook=common.decode_unicode_hook)
        # determine if good to go
        readyToGo = True
        command_function = None
        responses = {"status": 200, "msg": "OK"}
        # check netpass
        if conn_req["netpass"] != self.netPass:
            readyToGo = False
            responses.setdefault("errors", []).append("invalid netpass")
        # check script info
        if conn_req["scriptname"] != self.varDict["scriptname"]:
            readyToGo = False
            responses.setdefault("errors", []).append("invalid scriptname: {}".format(conn_req["scriptname"]))
        if conn_req["version"] != self.varDict["version"]:
            readyToGo = False
            responses.setdefault("errors", []).append("invalid version")
        try:
            command_function = self.endpointManager.get_command(conn_req["command"])
        except KeyError, e:
            readyToGo = False
            responses.setdefault("errors", []).append("command not recognized: %s" % conn_req["command"])
        finally:
            # if ready to go, send confirmation and continue
            if readyToGo:
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
                responses["downloadAddrIP"] = self.varDict["downloadAddrIP"]
                responses["downloadAddrLoc"] = self.varDict["downloadAddrLoc"]
                responses["scriptname"] = self.varDict["scriptname"]
                responses["version"] = self.varDict["version"]
                conn_resp = json.dumps(responses)
                s.sendall(conn_resp)
