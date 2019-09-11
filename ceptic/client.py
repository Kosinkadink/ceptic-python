import getopt
import json
import os
import socket

from sys import version_info
from ceptic.network import SocketCeptic
from ceptic.common import CepticAbstraction,CepticSettings,CepticCommands,decode_unicode_hook
from ceptic.managers.endpointmanager import EndpointManager
from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,CertificateConfiguration


class CepticClientSettings(CepticSettings):
    """
    Class used to store client settings. Can be expanded upon by directly adding variables to settings dictionary
    """
    def __init__(self, name="template", version="1.0.0", send_cache=409600, location=os.getcwd()):
        CepticSettings.__init__(self)
        self.settings["name"] = str(name)
        self.settings["version"] = str(version)
        self.settings["send_cache"] = int(send_cache)
        self.settings["location"] = str(location)


class CepticClient(CepticAbstraction):

    def __init__(self, settings, certificate_config=None):
        self.settings = settings
        # initialize CepticAbstraction
        CepticAbstraction.__init__(self)
        self.shouldExit = False
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

    def exit(self):
        """
        Properly begin to exit client; sets shouldExit to True, performs clean_processes()
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
