#!/usr/bin/python2

import getopt
import json
import os
import socket

from sys import version_info
import ceptic.common as common
from ceptic.common import CepticAbstraction
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException


def main(argv, template_client, location, start_terminal=True):
    """
    Wrapper function for starting a ceptic client via terminal
    :param argv: arguments from terminal input
    :param template_client: ceptic client class
    :param location: absolute directory to treat as location
    :param start_terminal: boolean to determine if a user input loop should be started
    :return: None
    """
    template_client(location, start_terminal=start_terminal)


# sort of an abstract class; will not work on its own
class CepticClient(CepticAbstraction):
    # don't change this
    netPass = None
    startTerminal = True
    __location__ = None
    nullVarDict = dict(send_cache="None", scriptname="None", version="None")
    nullFuncMap = dict(NULL=None)
    # change this to default values
    varDict = dict(send_cache=409600, scriptname='template', version='3.0.0')

    def __init__(self, location=os.getcwd(), start_terminal=True, name='template', version='1.0.0', client_verify=True):
        # set varDict arguments
        self.varDict["scriptname"] = name
        self.varDict["version"] = version
        # initialize CepticAbstraction
        CepticAbstraction.__init__(self, location)
        self.startTerminal = start_terminal
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
        self.certificateManager = CertificateManager(CertificateManager.CLIENT, self.fileManager, client_verify=client_verify)
        # do initialization
        self.initialize()

    def initialize(self):
        """
        Initialize client configuration and processes
        :return: None
        """
        # perform all tasks
        self.init_spec()
        self.netPass = self.fileManager.get_netpass()
        self.certificateManager.generate_context_tls()
        self.run_processes()

    def run_processes(self):
        """
        Attempts to start terminal wrapper if variable startTerminal is true
        :return: None
        """
        if self.startTerminal:
            # now start terminal wrapper
            self.terminal_wrapper()

    def init_spec(self):
        """
        Initialize specific ceptic instance files
        :return: None
        """
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
        """
        Function to overload for more specific initialization
        :return: None
        """
        pass

    def connect_with_null_dict(self, ip):
        return self.connect_ip(ip, "NULL", None, varDictToUse=self.nullVarDict)

    def ping_terminal_command(self, ip):
        return self.connect_ip(ip, "ping", None)

    def ping_endpoint(self, s, data=None, data_to_store=None):
        """
        Simple endpoint, sends pong to client
        :param s: SocketCeptic instance
        :param data: additional data to deliver to the server
        :param data_to_store: additional data to NOT send to server but keep for local reference
        :return: success state
        """
        received_msg = s.recv(4)
        return {"status": 200, "msg": received_msg}

    def connect_ip(self, ip, command=None, data=None, dataToStore=None, varDictToUse=None):  # connect to ip
        """
        Connect to ceptic server at given ip
        :param ip: string ip:port address, written as XXX.XXX.XXX.XXX:XXXX
        :param data: data to be inserted into json to send to server
        :param command: name of command to perform for client-server
        :param dataToStore: optional data to NOT send to the server but keep for local reference
        :param varDictToUse: optional variable dictionary to use instead of default client varDict
        :return: depends on data returned by command's function
        """
        if not command:
            raise ValueError("command must be provided")

        if not varDictToUse:
            varDictToUse = self.varDict
        try:
            host = ip.split(':')[0]
            port = int(ip.split(':')[1])
        except:
            return {"status": 404, "msg":"invalid host/port provided"}
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(5)
        try:
            s.connect((host, port))
        except Exception as e:
            print("closing connection: {}".format(str(e)))
            s.close()
            return {"status": 404, "msg": "Server at {} not available".format(ip)}
        print("\nConnection successful to " + ip)
        return self.connect_protocol_client(s, command, data, dataToStore, varDictToUse)

    def connect_protocol_client(self, s, command, data, dataToStore, varDictToUse=varDict):
        """
        Perform general ceptic protocol handshake to continue connection
        :param s: socket created in connect_ip (socket.socket)
        :param data: data to be inserted into json to send to server
        :param command: name of command to perform for client-server
        :param dataToStore: data to NOT send to the server but keep for local reference
        :param varDictToUse: optional variable dictionary to use instead of default client varDict
        :return:
        """
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = self.certificateManager.wrap_socket(s)
        except CertificateManagerException as e:
            return {"status": 400, "msg": str(e)}
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
            print("failure. closing connection: {0}:{1}:{2},{3},{4}".format(conn_resp["status"], conn_resp["msg"],
                                                                            conn_resp["downloadAddrIp"],
                                                                            conn_resp["downloadAddrLoc"],
                                                                            conn_resp["errors"]))
            return conn_resp
        else:
            print("success. continuing...")
            return_val = command_function(s, data, dataToStore)
            s.close()
            return return_val

    def boot(self):
        self.clear()
        print("TechTem {} Client started".format(self.varDict["scriptname"].capitalize()))
        print("Version {}".format(self.varDict["version"]))
        print("Type help for command list\n")

    def help(self):
        print("\nclear: clears screen")
        print("exit: closes program")

    def terminal_wrapper(self):
        """
        Wrapper for client input, loops waiting for user input
        :return: None
        """
        self.boot()
        while not self.shouldExit:
            if version_info < (3,0): # python2 code
                inp = raw_input(">")
            else:
                inp = input(">")
            returned = self.service_terminal(inp)
            if returned is not None:
                print(returned)

    def exit(self):
        """
        Properly begin to exit server; sets shouldExit to True, performs clean_processes()
        :return: None
        """
        self.clean_processes()
        self.shouldExit = True

    def clean_processes(self):
        """
        Function to overload to perform cleaning before exit
        :return: None
        """
        pass
