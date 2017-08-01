#!/usr/bin/python2

import ast
import getopt
import json
import os
import select
import socket
import ssl
import threading
from time import sleep

import ceptic.common as common
from ceptic.common import CepticAbstraction


def main(argv, templateServer, location):
    startRawInput = True
    portS = None
    try:
        opts, args = getopt.getopt(argv, 'tp:', ['port='])
    except getopt.GetoptError:
        print('-p [port] or --port [port] only')
        quit()
    for opt, arg in opts:
        if opt in ("-p", "--port"):
            portS = arg
        if opt in ("-t"):
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
    threads = []
    pipes = []
    startTime = None
    context = None
    netPass = None
    __location__ = None
    # change this to default values
    varDict = dict(version='3.0.0', serverport=9999, userport=10999, useConfigPort=True, send_cache=409600,
                   scriptname=None, name='template', downloadAddrIP='jedkos.com:9011',
                   downloadAddrLoc='protocols/template.py')

    # form is ip:port&&location/on/filetransferserver/file.py

    def __init__(self, location, serve=varDict["serverport"], user=varDict["userport"], startUser=True):
        CepticAbstraction.__init__(self, location)
        self.__location__ = location
        if serve is not None:
            self.varDict["useConfigPort"] = False
            self.varDict["serverport"] = int(serve)
        self.startUser = startUser
        self.shouldExit = False
        self.funcMap = {}  # fill in with a string key and a function value
        self.terminalMap = {"exit": (lambda data: self.exit()), "clear": (lambda data: self.clear()),
                            "info": (lambda data: self.info())}

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
        # make directories if don't exist
        print self.__location__
        if not os.path.exists(self.__location__ + '/resources'): os.makedirs(self.__location__ + '/resources')
        if not os.path.exists(self.__location__ + '/resources/protocols'): os.makedirs(
            self.__location__ + '/resources/protocols')  # for protocol scripts
        if not os.path.exists(self.__location__ + '/resources/cache'): os.makedirs(
            self.__location__ + '/resources/cache')  # used to store info for protocols and client
        if not os.path.exists(self.__location__ + '/resources/programparts'): os.makedirs(
            self.__location__ + '/resources/programparts')  # for storing protocol files
        if not os.path.exists(self.__location__ + '/resources/uploads'): os.makedirs(
            self.__location__ + '/resources/uploads')  # used to store files for upload
        if not os.path.exists(self.__location__ + '/resources/downloads'): os.makedirs(
            self.__location__ + '/resources/downloads')  # used to store downloaded files
        if not os.path.exists(self.__location__ + '/resources/networkpass'): os.makedirs(
            self.__location__ + '/resources/networkpass')  # contains network passwords
        # perform all tasks
        self.generateContextTLS()
        self.init_spec()
        # config stuff
        self.loadConfig()
        self.netPass = self.get_netPass(self.__location__)
        self.run_processes()

    def loadConfig(self):
        # load config values, or create default file
        self.varDict = self.config(self.varDict, self.__location__)
        # reassign values
        self.varDict["serverport"] = int(self.varDict["serverport"])
        self.varDict["userport"] = int(self.varDict["userport"])
        self.varDict["send_cache"] = int(self.varDict["send_cache"])

    def generateContextTLS(self):
        cert_loc = os.path.join(self.__location__, 'resources/source/certification')
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=os.path.join(cert_loc, 'techtem_cert.pem'),
                                     keyfile=os.path.join(cert_loc, 'techtem_server_key.pem'))
        self.context.load_verify_locations(cafile=os.path.join(cert_loc, 'techtem_cert_client.pem'))
        self.context.verify_mode = ssl.CERT_REQUIRED

    def init_spec(self):
        # insert application-specific initialization code here
        if not os.path.exists(self.__location__ + '/resources/programparts/%s' % self.varDict["name"]):
            os.makedirs(self.__location__ + '/resources/programparts/%s' % self.varDict["name"])
        self.init_spec_extra()

    def init_spec_extra(self):
        pass

    def serverterminal(self, inp):  # used for server commands
        user_inp = inp.split()
        if not user_inp:
            pass
        try:
            return self.terminalMap[user_inp[0]](user_inp)
        except KeyError, e:
            print str(e)
            print("ERROR: terminal command {} is not recognized".format(user_inp[0]))

    def info(self):  # display current configuration
        print("INFORMATION:")
        print("name: %s" % self.varDict["name"])
        print("version: %s" % self.varDict["version"])
        print("serverport: %s" % self.varDict["serverport"])
        print("userport: %s" % self.varDict["userport"])
        print("send_cache: %s" % self.varDict["send_cache"])
        print("scriptname: %s" % self.varDict["scriptname"])
        print("downloadAddrIP: %s" % self.varDict["downloadAddrIP"])
        print("downloadAddrLoc: %s" % self.varDict["downloadAddrLoc"])
        print("")

    def exit(self):
        self.shouldExit = True
        self.cleanProcesses()

    def cleanProcesses(self):
        pass

    def servergen(self, repeatFunc=None):
        print('%s server started - version %s on port %s\n' % (
            self.varDict["name"], self.varDict["version"], self.varDict["serverport"]))
        self.get_netPass(self.__location__)
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
                    self.serverterminal(userinp)
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
        s = self.context.wrap_socket(s, server_side=True)
        # wrap socket with SocketCeptic, to send length of message first
        s = common.SocketCeptic(s)
        # receive connection request
        client_request = s.recv(1024)
        conn_req = ast.literal_eval(client_request)
        # determine if good to go
        readyToGo = True
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
            func = self.funcMap[conn_req["command"]]
        except KeyError, e:
            readyToGo = False
            responses.setdefault("errors", []).append("command not recognized: %s" % conn_req["command"])
        # if ready to go, send confirmation and continue
        if readyToGo:
            conn_resp = json.dumps(responses)
            s.sendall(conn_resp)
            if conn_req["data"] is None:
                func(s)
            else:
                func(s, conn_req["data"])
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
