#!/usr/bin/python2

import ast
import json
import os
import socket
import ssl

import ceptic.common as common
from ceptic.common import CepticAbstraction


# sort of an abstract class; will not work on its own
class CepticClientTemplate(CepticAbstraction):
    # don't change this
    threads = []
    context = None
    netPass = None
    startTerminal = True
    __location__ = None
    # change this to default values
    standalone = False
    default_command = None
    varDict = dict(send_cache=409600, scriptname='template', version='3.0.0')
    nullVarDict = dict(send_cache="None", scriptname="None", version="None")
    funcMap = dict()  # fill with string:functions pairs
    nullFuncMap = dict(NULL=None)

    def __init__(self, location, startTerminal):
        CepticAbstraction.__init__(self, location)
        self.injectSpecificCode()
        self.startTerminal = startTerminal
        self.shouldExit = False
        self.standalone = True
        self.terminalMap = {"exit": (lambda data: self.exit()), "clear": (lambda data: self.boot()),
                            "help": (lambda data: self.help())}
        self.initialize()

    def run_processes(self):
        if self.startTerminal:
            # now start terminal wrapper
            self.terminalwrapper()

    def process_list_to_dict(self, input_list):
        """
        Transform a list of strings into proper dictionary output to be sent to server
        :param input_list: list
        :return: dictionary to use as data
        """
        return {"default": input_list[0]}

    def set_terminalMap(self):
        pass

    def set_funcMap(self):
        pass

    def add_to_funcMap(self, command, func):
        self.funcMap[command] = func

    def add_to_terminalMap(self, command, func):
        self.terminalMap[command] = func

    def set_default_command(self, command):
        if command is not None:
            self.varDict["default_command"] = command

    def add_var_to_dict(self, key, val):
        self.varDict[key] = val

    def get_default_command(self):
        try:
            return self.varDict["default_command"]
        except KeyError:
            return None

    def perform_default_command(self, input=None):
        def_inp = [self.default_command]
        if not input:
            pass
        elif isinstance(input, list):
            def_inp.extend(input)
        else:
            def_inp.append(input)
        return self.terminalMap[self.default_command](def_inp)

    def initialize(self):
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
        self.generateContextTLS()
        self.netPass = self.get_netPass(self.__location__)
        self.init_spec()
        self.set_terminalMap()
        self.set_funcMap()
        self.run_processes()

    def injectSpecificCode(self):
        pass

    def generateContextTLS(self):
        cert_loc = os.path.join(self.__location__, 'resources/source/certification')
        self.context = ssl.create_default_context()
        self.context.load_cert_chain(certfile=os.path.join(cert_loc, 'techtem_cert_client.pem'),
                                     keyfile=os.path.join(cert_loc, 'techtem_client_key.pem'))
        self.context.check_hostname = False
        self.context.load_verify_locations(cafile=os.path.join(cert_loc, 'techtem_cert.pem'))

    def init_spec(self):
        if not os.path.exists(self.__location__ + '/resources/programparts/%s' % self.varDict["scriptname"]):
            os.makedirs(self.__location__ + '/resources/programparts/%s' % self.varDict["scriptname"])

        if not os.path.exists(
                        self.__location__ + '/resources/programparts/%s/serverlist.txt' % self.varDict["scriptname"]):
            with open(self.__location__ + '/resources/programparts/%s/serverlist.txt' % self.varDict["scriptname"],
                      "a") as seeds:
                seeds.write("""####################################################
# The format is: ip:port
# Files will be sent to and from these servers
# Lines NOT starting with # will be read
####################################################""")
        self.init_spec_extra()

    def init_spec_extra(self):
        pass

    def connect_with_null_dict(self, ip):
        return self.connectip(ip, "None", "NULL", funcMapping=self.nullFuncMap, varDictToUse=self.nullVarDict)

    def connectip(self, ip, data, command, funcMapping=funcMap, dataToStore=None, varDictToUse=None):  # connect to ip
        if not varDictToUse:
            varDictToUse = self.varDict
        try:
            host = ip.split(':')[0]
            port = int(ip.split(':')[1])
        except:
            return 'invalid host/port provided\n'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((host, port))
        except:
            print 'closing connection :('
            s.close()
            return "Server at " + ip + " not available\n"
        print "\nConnection successful to " + ip
        return self.connectprotocolclient(s, data, command, funcMapping, dataToStore, varDictToUse)

    def connectprotocolclient(self, s, data, command, funcMapping,
                              dataToStore, varDictToUse=varDict):  # communicate via protocol to command seed
        # wrap socket with TLS, handshaking happens automatically
        s = self.context.wrap_socket(s)
        # wrap socket with socketCeptic, to send length of message first
        s = common.socketCeptic(s)
        # create connection request
        conn_req = json.dumps({
            "netpass": self.netPass,
            "scriptname": varDictToUse["scriptname"],
            "version": varDictToUse["version"],
            "command": command,
            "data": data
        })
        # check if command exists; stop connection if not
        try:
            func = funcMapping[command]
        except KeyError, e:
            s.close()
            return {"status": 499, "msg": "client does not recognize command: %s" % command}
        # send connection request
        s.sendall(conn_req)
        # get response from server
        conn_resp = ast.literal_eval(s.recv(1024))
        # determine if good to go
        if conn_resp["status"] != 200:
            s.close()
            print "failure. closing connection: {0}:{1}:{2},{3},{4}".format(conn_resp["status"], conn_resp["msg"],
                                                                            conn_resp["downloadAddrIP"],
                                                                            conn_resp["downloadAddrLoc"],
                                                                            conn_resp["errors"])
            return conn_resp
        else:
            print "success. continuing..."
            return func(s, data, dataToStore)

    def boot(self):
        self.clear()
        print("TechTem {} Client started".format(self.varDict["scriptname"].capitalize()))
        print("Version {}".format(self.varDict["version"]))
        print("Type help for command list\n")

    def help(self):
        print "\nclear: clears screen"
        print "exit: closes program"

    def terminalwrapper(self):
        self.boot()
        while not self.shouldExit:
            inp = raw_input(">")
            print self.serverterminal(inp)

    def serverterminal(self, inp):  # used for server commands
        user_inp = inp.split()
        if not user_inp:
            print("no inp")
        try:
            return self.terminalMap[user_inp[0]](user_inp)
        except KeyError, e:
            print(str(e))
            print("ERROR: terminal command {} is not recognized".format(user_inp[0]))

    def exit(self):
        self.cleanProcesses()
        self.shouldExit = True

    def cleanProcesses(self):
        pass
