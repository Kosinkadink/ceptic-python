import getopt
import json
import os
import socket

from sys import version_info
import ceptic.common as common
from ceptic.common import CepticAbstraction, CepticSettings, CepticCommands
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,CertificateConfiguration


class CepticClientSettings(CepticSettings):
    """
    Class used to store client settings. Can be expanded upon by directly adding variables to varDict dictionary
    """
    def __init__(self, name="template", version="1.0.0", send_cache=409600, location=os.getcwd(), start_terminal=False):
        CepticSettings.__init__(self)
        self.varDict["name"] = str(name)
        self.varDict["version"] = str(version)
        self.varDict["send_cache"] = int(send_cache)
        self.varDict["location"] = str(location)
        self.varDict["start_terminal"] = boolean(start_terminal)


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

    def __init__(self, settings, certificate_config=None):
        self.settings = settings
        # initialize CepticAbstraction
        CepticAbstraction.__init__(self)
        self.startTerminal = start_terminal
        self.shouldExit = False
        # set up basic terminal endpoints
        self.terminalManager.add_endpoint("exit", lambda data: self.exit())
        self.terminalManager.add_endpoint("clear", lambda data: self.boot())
        self.terminalManager.add_endpoint("help", lambda data: self.help())
        self.add_terminal_endpoints()
        # set up endpoints
        self.endpointManager = EndpointManager.client()
        self.add_endpoints()
        # set up certificate manager
        self.certificateManager = CertificateManager.client(config=certificate_config)
        # do initialization
        self.initialize()

    def initialize(self):
        """
        Initialize client configuration and processes
        :return: None
        """
        # perform all tasks
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

    def run_processes(self):
        """
        Attempts to start terminal wrapper if variable startTerminal is true
        :return: None
        """
        if self.startTerminal:
            # now start terminal wrapper
            self.terminal_wrapper()

    def ping_terminal_endpoint(self, ip):
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

    def connect_ip(self, ip, type_name=None, endpoint=None, data=None, dataToStore=None):  # connect to ip
        """
        Connect to ceptic server at given ip
        :param ip: string ip:port address, written as XXX.XXX.XXX.XXX:XXXX
        :param data: data to be inserted into json to send to server
        :param endpoint: name of endpoint to perform for client-server
        :param dataToStore: optional data to NOT send to the server but keep for local reference
        :return: depends on data returned by endpoint's function
        """
        if not endpoint:
            raise ValueError("endpoint must be provided")

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
        print("Connection successful to {}".format(ip))
        return self.connect_protocol_client(s, endpoint, data, dataToStore)

    def connect_protocol_client(self, s, type_name, endpoint, data, dataToStore):
        """
        Perform general ceptic protocol handshake to continue connection
        :param s: socket created in connect_ip (socket.socket)
        :param data: data to be inserted into json to send to server
        :param endpoint: name of endpoint to perform for client-server
        :param dataToStore: data to NOT send to the server but keep for local reference
        :param self.settings: optional variable dictionary to use instead of default client varDict
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
            "type": type_name,
            "endpoint": endpoint,
            "data": data
        })
        # check if endpoint exists; stop connection if not
        try:
            endpoint_function = self.endpointManager.get_endpoint(type_name, endpoint)
        except KeyError:
            s.close()
            return {"status": 499, "msg": "client does not recognize endpoint: {} of type: {}".format(endpoint,type_name)}
        # send connection request
        s.sendall(conn_req)
        # get response from server
        conn_resp = json.loads(s.recv(1024), object_pairs_hook=common.decode_unicode_hook)
        # determine if good to go
        if conn_resp["status"] != 200:
            s.close()
            print("failure. closing connection: {0}:{1}:{2}".format(conn_resp["status"], conn_resp["msg"],
                                                                            conn_resp["errors"]))
            return conn_resp
        else:
            print("success. continuing...")
            return_val = endpoint_function(s, data, dataToStore)
            s.close()
            return return_val

    def boot(self):
        self.clear()
        print("{} Client started".format(self.settings["name"].capitalize()))
        print("Version {}".format(self.settings["version"]))
        print("Type help for endpoint list\n")

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
