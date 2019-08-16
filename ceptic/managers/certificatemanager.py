import os
import ssl
from ceptic.common import CepticException


class CerticateConfiguration(object):
    """
    Stores certificate info used to initialize CertificateManager
    """

    def __init__(self, certfile=None, keyfile=None, cafile=None, client_verify=True, check_hostname=True, secure=True):
        """
        Choose CertificateManager settings
        :param certfile: path of certfile - contains public key
        :param keyfile: path of keyfile - contains private key
        :param cafile: path of cafile - contains public key of other end of connection
        :param client_verify: boolean corresponding to if client verification is required
        :param check_hostname: boolean corresponding to if client should check hostname of server-submitted certificate
        :param secure: boolean corresponding to if CertificateManager should secure socket; unless specifically desired, it is RECOMMENDED this is kept true.
        If set to false, any certificates provided will be ignored, no wrapping will occur if wrapping function is called
        """
        self.certfile = certfile
        self.keyfile = keyfile
        self.cafile = cafile
        self.client_verify = client_verify
        self.check_hostname = check_hostname
        self.secure = secure


class CertificateManager(object):
    """
    Used to manage certificates for TLS in CEPtic implementations
    """
    SERVER = "__SERVER"
    CLIENT = "__CLIENT"
    REQUEST = None
    context = None

    def __init__(self, request, config=None):
        """
        Provide requester type and certificate information
        :param request: string representing type (CertificateManager.SERVER or CertificateManager.CLIENT)
        :param config: CertificateConfiguration with desired settings
        """
        self.show_warnings = True
        self.REQUEST_MAP = {
            self.SERVER: self.generate_context_server,
            self.CLIENT: self.generate_context_client
        }
        self.generate_context_tls = self.assign_request_type(request)
        self.config = config

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
        if self.context is None:
            self.generate_context_tls()
        is_server_side = self.REQUEST == self.SERVER
        if self.config.secure:
            try:
                return self.context.wrap_socket(socket, server_side=is_server_side)
            except ssl.SSLError as e:
                raise CertificateManagerException(str(e))
        else:
            if self.show_warnings:
                print("WARNING: 'secure' is set to false and no wrapping has occured; your socket is NOT secure. If this is not desired, reconfigure manager with CertificateConfiguration with 'secure' set to True")
            return socket

    def generate_context_tls(self, config=None):
        pass

    def generate_context_client(self, config=None):
        """
        Generate context for a client implementation
        :return: None
        """
        # if config is provided, replace currently stored one
        if config is not None:
            self.config = config
        # create SSL/TLS context from provided files
        self.context = ssl.create_default_context()
        # only load client cert + key if client verification is requested
        if self.client_verify:
            self.context.load_cert_chain(certfile=self.config.certfile,
                                         keyfile=self.config.keyfile)
        self.context.check_hostname = self.config.check_hostname
        self.context.load_verify_locations(cafile=self.config.cafile)

    def generate_context_server(self, config=None):
        """
        Generate context for a server implementation
        :return: None
        """
        # if config is provided, replace currently stored one
        if config is not None:
            self.config = config
        # create SSL/TLS context from provided files
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=self.config.certfile,
                                     keyfile=self.config.keyfile)
        # only check certs if client verification is requested
        if self.config.client_verify:
            self.context.load_verify_locations(cafile=self.config.cafile)
            self.context.verify_mode = ssl.CERT_REQUIRED


class CertificateManagerException(CepticException):
    pass
