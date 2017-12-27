import os
import ssl
from ceptic.common import CepticException


class CertificateManager(object):
    """
    Used to manage certificates for TLS in CEPtic implementations
    """
    SERVER = "__SERVER"
    CLIENT = "__CLIENT"
    REQUEST = None
    context = None

    def __init__(self, request, filemanager, certfile=None, keyfile=None, cafile=None):
        """
        Provide requester type and location directory
        :param request: string representing type (CertificateManager.SERVER or CertificateManager.CLIENT)
        :param filemanager: FileManager instance used by ceptic client/server
        :param certfile: path of certfile
        :param keyfile: path of keyfile
        :param cafile: path of cafile
        """
        self.fileManager = filemanager
        self.REQUEST_MAP = {
            self.SERVER: self.generate_context_server,
            self.CLIENT: self.generate_context_client
        }
        self.generate_context_tls = self.assign_request_type(request)
        self.certfile = certfile
        self.keyfile = keyfile
        self.cafile = cafile

    def assign_request_type(self, request):
        if request in [self.SERVER, self.CLIENT]:
            self.REQUEST = request
            return self.REQUEST_MAP[self.REQUEST]
        else:
            CertificateManagerException("requested manager type {} not valid".format(request))

    def wrap_socket(self, socket):
        """
        Wrapper for ssl package's context.wrap_socket function
        :param socket: some pure socket
        :return: socket wrapped in SSL/TLS
        """
        is_server_side = self.REQUEST == self.SERVER
        return self.context.wrap_socket(socket, server_side=is_server_side)

    def generate_context_tls(self, certfile=None, keyfile=None, cafile=None):
        pass

    def generate_context_client(self, certfile=None, keyfile=None, cafile=None):
        """
        Generate context for a client implementation
        :return: None
        """
        # if files are provided in method, replace file locations
        if certfile is not None:
            self.certfile = certfile
        if keyfile is not None:
            self.keyfile = keyfile
        if cafile is not None:
            self.cafile = cafile
        # add default cert locations if no file locations were ever provided
        if self.certfile is None:
            self.certfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_client.pem')
        if self.keyfile is None:
            self.keyfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_key_client.pem')
        if self.cafile is None:
            self.cafile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_server.pem')
        # create SSL/TLS context from provided files
        self.context = ssl.create_default_context()
        self.context.load_cert_chain(certfile=self.certfile,
                                     keyfile=self.keyfile)
        self.context.check_hostname = False
        self.context.load_verify_locations(cafile=self.cafile)

    def generate_context_server(self, certfile=None, keyfile=None, cafile=None):
        """
        Generate context for a server implementation
        :return: None
        """
        # if files are provided in method, replace file locations
        if certfile is not None:
            self.certfile = certfile
        if keyfile is not None:
            self.keyfile = keyfile
        if cafile is not None:
            self.cafile = cafile
        # add default cert locations if no file locations were ever provided
        if self.certfile is None:
            self.certfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_server.pem')
        if self.keyfile is None:
            self.keyfile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_key_server.pem')
        if self.cafile is None:
            self.cafile = os.path.join(self.fileManager.get_directory("certification"), 'techtem_cert_client.pem')
        # create SSL/TLS context from provided files
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=self.certfile,
                                     keyfile=self.keyfile)
        self.context.load_verify_locations(cafile=self.cafile)
        self.context.verify_mode = ssl.CERT_REQUIRED


class CertificateManagerException(CepticException):
    pass
