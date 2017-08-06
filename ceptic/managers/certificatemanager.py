import os
import ssl
from ceptic.common import CepticException

class CertificateManager(object):
    """
    Used to manage certificates for TLS in CEPtic implementations
    """
    SERVER = "__SERVER"
    CLIENT = "__CLIENT"
    REQUESTER = None
    context = None

    def __init__(self, request, filemanager, certfile=None, keyfile=None, cafile=None):
        """
        Provide requester type and location directory
        :param request: string representing type (CertificateManager.SERVER or CertificateManager.CLIENT)
        :param location: path of CEPtic implementation
        :param certfile: path of certfile
        :param keyfile: path of keyfile
        :param cafile: path of cafile
        """
        self.fileManager = filemanager
        self.REQUEST_MAP = {
            self.SERVER: self.generate_context_server,
            self.CLIENT: self.generate_context_client
        }
        self.assign_request_type(request)
        self.certfile = certfile
        self.keyfile = keyfile
        self.cafile = cafile

    def assign_request_type(self, request):
        if request in [self.SERVER, self.CLIENT]:
            self.REQUESTER = request
            self.generateContextTLS = self.REQUEST_MAP[self.REQUESTER]
        else:
            CertificateManagerException("requested manager type {} not valid".format(request))

    def wrap_socket(self, socket):
        """
        Wrapper for ssl package's context.wrap_socket function
        :param socket: some pure socket
        :return: socket wrapped in SSL/TLS
        """
        is_server_side = self.REQUESTER == self.SERVER
        return self.context.wrap_socket(socket, server_side=is_server_side)

    def generateContextTLS(self):
        pass

    def generate_context_client(self):
        """
        Generate context for a client implementation
        :return: None
        """
        if self.certfile is None:
            self.certfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_client.pem')
        if self.keyfile is None:
            self.keyfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_client_key.pem')
        if self.cafile is None:
            self.cafile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_server.pem')
        self.context = ssl.create_default_context()
        self.context.load_cert_chain(certfile=self.certfile,
                                     keyfile=self.keyfile)
        self.context.check_hostname = False
        self.context.load_verify_locations(cafile=self.cafile)

    def generate_context_server(self):
        """
        Generate context for a server implementation
        :return: None
        """
        if self.certfile is None:
            self.certfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_server.pem')
        if self.keyfile is None:
            self.keyfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_server_key.pem')
        if self.cafile is None:
            self.cafile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_client.pem')
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=self.certfile,
                                     keyfile=self.keyfile)
        self.context.load_verify_locations(cafile=self.cafile)
        self.context.verify_mode = ssl.CERT_REQUIRED


class CertificateManagerException(CepticException):
    def __init__(self, *args):
        CepticException.__init__(self, *args)
