import os
import ssl
from ceptic.common import CepticException


def create_ssl_config(certfile=None, keyfile=None, cafile=None, check_hostname=True, secure=True, ssl_context=None):
    """
    Choose CertificateManager settings
    :param certfile: path of certfile - contains public key
    :param keyfile: path of keyfile - contains private key
    :param cafile: path of cafile - contains public key of other end of connection
    :param check_hostname: boolean corresponding to if client should check hostname of server-submitted certificate
    :param secure: boolean corresponding to if CertificateManager should secure socket; unless specifically desired, it is RECOMMENDED this is kept true.
    If set to false, any certificates provided will be ignored, no wrapping will occur if wrapping function is called
    :param ssl_context: 
    """
    settings = {}
    settings["certfile"] = certfile
    settings["keyfile"] = keyfile
    settings["cafile"] = cafile
    settings["check_hostname"] = check_hostname
    settings["secure"] = secure
    settings["ssl_context"] = ssl_context
    return settings


class CertificateManager(object):
    """
    Used to manage certificates for TLS in CEPtic implementations
    """
    SERVER = "__SERVER"
    CLIENT = "__CLIENT"
    REQUEST = None

    def __init__(self, request, ssl_config=None):
        """
        Provide requester type and certificate information
        :param request: string representing type (CertificateManager.SERVER or CertificateManager.CLIENT)
        :param ssl_config: CertificateConfiguration with desired settings
        """
        self.ssl_context = None
        self.show_warnings = True
        self.REQUEST_MAP = {
            self.SERVER: self.generate_context_server,
            self.CLIENT: self.generate_context_client
        }
        self.generate_context_tls = self.assign_request_type(request)
        self.ssl_config = ssl_config
        self.secure = True

    @classmethod
    def client(cls, ssl_config=None):
        return cls(cls.CLIENT, ssl_config)

    @classmethod
    def server(cls, ssl_config=None):
        return cls(cls.SERVER, ssl_config)

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
        if self.ssl_context is None:
            self.generate_context_tls()
        is_server_side = self.REQUEST == self.SERVER
        if self.ssl_config["secure"]:
            try:
                return self.ssl_context.wrap_socket(socket, server_side=is_server_side)
            except ssl.SSLError as e:
                raise CertificateManagerException(str(e))
        else:
            if self.show_warnings:
                print("WARNING: 'secure' is set to false and no wrapping has occured; your socket is NOT secure. If this is not desired, reconfigure manager with CertificateConfiguration with 'secure' set to True")
            return socket

    def generate_context_tls(self, ssl_config=None):
        pass

    def generate_context_client(self, ssl_config=None):
        """
        Generate context for a client implementation
        :return: None
        """
        # if ssl_config is provided here, replace currently stored one
        if ssl_config is not None:
            self.ssl_config = ssl_config
        # if no ssl_config at all in manager, assume no security to be provided
        if self.ssl_config is None:
            self.ssl_config = create_ssl_config(secure=False)
        # if ssl_context is provided in config, use it
        if self.ssl_config["ssl_context"] is not None:
            self.ssl_context = self.ssl_config["ssl_context"]
            return
        # if ssl_config is set to not be secure, do not attempt to create a context
        if not self.ssl_config["secure"]:
            if self.show_warnings:
                print("WARNING: 'secure' is set to false and no wrapping has occured; your socket is NOT secure. If this is not desired, reconfigure manager with CertificateConfiguration with 'secure' set to True")
            return
        # create SSL/TLS context from provided files
        self.ssl_context = ssl.create_default_context()
        # only load client cert + key if client verification is requested
        # if only cert or if only key is provided, raise exception
        if self.ssl_config["certfile"] is not None:
            if self.ssl_config["keyfile"] is None:
                raise CertificateManagerException("certfile was provided but keyfile was not; either both files or neither are expected")
            self.ssl_context.load_cert_chain(certfile=self.ssl_config["certfile"],
                                         keyfile=self.ssl_config["keyfile"])
        else:
            if self.ssl_config["keyfile"] is not None:
                raise CertificateManagerException("keyfile was provided but certfile was not; either both files or neither are expected")
        self.ssl_context.check_hostname = self.ssl_config["check_hostname"]
        if self.ssl_config["cafile"] is not None:
            self.ssl_context.load_verify_locations(cafile=self.ssl_config["cafile"])

    def generate_context_server(self, ssl_config=None):
        """
        Generate context for a server implementation
        :return: None
        """
        # if ssl_config is provided, replace currently stored one
        if ssl_config is not None:
            self.ssl_config = ssl_config
        # if no ssl_config at all in manager, assume no security requested
        if self.ssl_config is None:
            self.ssl_config = create_ssl_config(secure=False)
        # if ssl_context is provided in config, use it
        if self.ssl_config["ssl_context"] is not None:
            self.ssl_context = self.ssl_config["ssl_context"]
            return
        # if ssl_config is set to not be secure, do not attempt to create a context
        if not self.ssl_config["secure"]:
            return
        # create SSL/TLS  context from provided files
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if self.ssl_config["certfile"] is not None and self.ssl_config["keyfile"] is not None:
            self.ssl_context.load_cert_chain(certfile=self.ssl_config["certfile"],
                                         keyfile=self.ssl_config["keyfile"])
        else:
            raise CertificateManagerException("ssl_context expects keyfile and certfile to not be None for secure option; one or both were None")
        # only check certs if client verification is requested
        if self.ssl_config["cafile"] is not None:
            self.ssl_context.load_verify_locations(cafile=self.ssl_config["cafile"])
            self.ssl_context.verify_mode = ssl.CERT_REQUIRED


class CertificateManagerException(CepticException):
    pass
