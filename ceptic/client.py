#!/usr/bin/python2

import json
import os
import socket

import ceptic.common as common
from ceptic.common import CepticAbstraction
from ceptic.managers.certificatemanager import CertificateManager


# sort of an abstract class; will not work on its own
class CepticClientTemplate(CepticAbstraction):
    # don't change this
    netPass = None
    startTerminal = True
    __location__ = None
    nullVarDict = dict(send_cache="None", scriptname="None", version="None")
    nullFuncMap = dict(NULL=None)
    # change this to default values
    varDict = dict(send_cache=409600, scriptname='template', version='3.0.0')

    def __init__(self, location, startTerminal):
        CepticAbstraction.__init__(self, location)
        self.startTerminal = startTerminal
        self.shouldExit = False
        # set up basic terminal commands
        self.terminalManager.add_command("exit", lambda data: self.exit())
        self.terminalManager.add_command("clear", lambda data: self.boot())
        self.terminalManager.add_command("help", lambda data: self.help())
        self.add_terminal_commands()
        # set up endpoints
        self.endpointManager.add_command("ping", self.ping_endpoint)
        self.add_endpoint_commands()
        # set up certificate manager
        self.certificateManager = CertificateManager(CertificateManager.CLIENT, self.fileManager)
        # do initialization
        self.initialize()

    def initialize(self):
        # perform all tasks
        self.init_spec()
        self.netPass = self.fileManager.get_netpass()
        self.certificateManager.generate_context_tls()
        self.run_processes()

    def run_processes(self):
        if self.startTerminal:
            # now start terminal wrapper
            self.terminalwrapper()

    def init_spec(self):
        # add specific program parts directory to fileManager
        self.fileManager.add_directory("specificparts", self.varDict["scriptname"], base_key="programparts")
        self.fileManager.add_file("serverlistfile", "serverlist.txt", base_key="specificparts",
                                  text="""####################################################
# The format is: ip:port
# Files will be sent to and from these servers
# Lines NOT starting with # will be read
####################################################""")
        # more initialization for specific applications
        self.init_spec_extra()

    def init_spec_extra(self):
        pass

    def connect_with_null_dict(self, ip):
        return self.connectip(ip, "None", "NULL", varDictToUse=self.nullVarDict)

    def ping_terminal_command(self, ip):
        return self.connectip(ip, None, "ping")

    def ping_endpoint(self, s, data=None, dataToStore=None):
        """
        Simple endpoint, sends pong to client
        :param s: SocketCeptic instance
        :param data: additional data
        :return: success state
        """
        received_msg = s.recv(4)
        return {"status": 200, "msg": received_msg}

    def connectip(self, ip, data, command, dataToStore=None, varDictToUse=None):  # connect to ip
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
        except Exception, e:
            print("closing connection: {}".format(str(e)))
            s.close()
            return "Server at " + ip + " not available\n"
        print("\nConnection successful to " + ip)
        return self.connectprotocolclient(s, data, command, dataToStore, varDictToUse)

    def connectprotocolclient(self, s, data, command, dataToStore, varDictToUse=varDict):
        # wrap socket with TLS, handshaking happens automatically
        s = self.certificateManager.wrap_socket(s)
        # wrap socket with SocketCeptic, to send length of message first
        s = common.SocketCeptic(s)
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
            command_function = self.endpointManager.get_command(command)
        except KeyError:
            s.close()
            return {"status": 499, "msg": "client does not recognize command: %s" % command}
        # send connection request
        s.sendall(conn_req)
        # get response from server
        conn_resp = json.loads(s.recv(1024), object_pairs_hook=common.decode_unicode_hook)
        # determine if good to go
        if conn_resp["status"] != 200:
            s.close()
            print "failure. closing connection: {0}:{1}:{2},{3},{4}".format(conn_resp["status"], conn_resp["msg"],
                                                                            conn_resp["downloadAddrIp"],
                                                                            conn_resp["downloadAddrLoc"],
                                                                            conn_resp["errors"])
            return conn_resp
        else:
            print "success. continuing..."
            return command_function(s, data, dataToStore)

    def boot(self):
        self.clear()
        print("TechTem {} Client started".format(self.varDict["scriptname"].capitalize()))
        print("Version {}".format(self.varDict["version"]))
        print("Type help for command list\n")

    def help(self):
        print("\nclear: clears screen")
        print("exit: closes program")

    def terminalwrapper(self):
        self.boot()
        while not self.shouldExit:
            inp = raw_input(">")
            returned = self.service_terminal(inp)
            if returned is not None:
                print returned

    def exit(self):
        self.cleanProcesses()
        self.shouldExit = True

    def cleanProcesses(self):
        pass
