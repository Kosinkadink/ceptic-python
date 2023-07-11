import re

from ssl import SSLContext
from typing import Union

from ceptic.common import CepticException


# region Exceptions
class SecurityException(CepticException):
    """
    Security-related Ceptic exception.
    """
    pass


class SecurityPEMException(SecurityException):
    """
    Security exception related to parsing of certificate/key files.
    """
    pass
# endregion


class SecuritySettings(object):
    """
    Settings determining certificates/keys used (if any) for a Server or Client.
    """

    def __init__(self, ssl_context: SSLContext = None) -> None:
        self.local_cert: Union[str, None] = None
        self.local_key: Union[str, None] = None
        self.remote_cert: Union[str, None] = None
        self.remote_certs_path: Union[str, None] = None
        self.verify_remote: bool = True
        self.secure: bool = True
        self._key_password: Union[str, None] = None
        self.ssl_context: Union[SSLContext, None] = ssl_context

    @property
    def key_password(self) -> Union[str, None]:
        value = self._key_password
        self._key_password = None
        return value

    @key_password.setter
    def key_password(self, password: Union[str, None]) -> None:
        self._key_password = password

    @classmethod
    def client_unsecure(cls) -> 'SecuritySettings':
        settings = cls()
        settings.secure = False
        return settings

    @classmethod
    def client(cls, local_cert: str = None, local_key: str = None, remote_cert: str = None,
               remote_certs_path: str = None, verify_remote: bool = True) -> 'SecuritySettings':
        settings = cls()
        settings.local_cert = local_cert
        settings.local_key = local_key
        settings.remote_cert = remote_cert
        settings.remote_certs_path = remote_certs_path
        settings.verify_remote = verify_remote
        return settings

    @classmethod
    def server_unsecure(cls) -> 'SecuritySettings':
        settings = cls()
        settings.secure = False
        return settings

    @classmethod
    def server(cls, local_cert: str = None, local_key: str = None, remote_cert: str = None,
               remote_certs_path: str = None) -> 'SecuritySettings':
        settings = cls()
        settings.local_cert = local_cert
        settings.local_key = local_key
        settings.remote_cert = remote_cert
        settings.remote_certs_path = remote_certs_path
        return settings


class CertificateHelper(object):
    PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN ([A-Z ]+)-----([\s\S]*?)-----END [A-Z ]+-----")

    BEGIN_STRING = "-----BEGIN "

    RSA_PRIVATE_KEY = "RSA PRIVATE KEY"
    PRIVATE_KEY = "PRIVATE KEY"
    ENCRYPTED_PRIVATE_KEY = "ENCRYPTED PRIVATE KEY"

    RSA_PUBLIC_KEY = "RSA PUBLIC KEY"
    PUBLIC_KEY = "PUBLIC KEY"
    CERTIFICATE_STRING = "CERTIFICATE"


