import pytest

from ceptic.client import CepticClient, client_settings


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def client_all_files(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = client_settings()
        return CepticClient(settings, locations.c_certfile, locations.c_keyfile, locations.c_cafile,
                            check_hostname=check_hostname)
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def client_certfile_keyfile_only(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = client_settings()
        return CepticClient(settings, locations.c_certfile, locations.c_keyfile, check_hostname=check_hostname)
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def client_cafile_only(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = client_settings()
        return CepticClient(settings, cafile=locations.c_cafile, check_hostname=check_hostname)
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def client_no_files(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = client_settings()
        return CepticClient(settings, check_hostname=check_hostname)
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def client_not_secure(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = client_settings()
        return CepticClient(settings, check_hostname=check_hostname, secure=False)
    return _real_func
