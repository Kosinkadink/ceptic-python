from ceptic.client import CepticClient, ClientSettings
from ceptic.security import SecuritySettings
from ceptic.server import ServerSettings, CepticServer


def create_unsecure_server(settings: ServerSettings = None, verbose: bool = None) -> CepticServer:
    settings = settings if settings else ServerSettings(verbose=verbose is True)
    return CepticServer(security=SecuritySettings.server_unsecure(), settings=settings)


def create_unsecure_client(settings: ClientSettings = None) -> CepticClient:
    settings = settings if settings else ClientSettings()
    return CepticClient(settings=settings, security=SecuritySettings.client_unsecure())


def create_secure_server(settings: ServerSettings = None, verbose: bool = None) -> CepticServer:
    pass


def create_secure_client(settings: ClientSettings = None) -> CepticClient:
    pass

