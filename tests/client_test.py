import os
import pytest
from ceptic.client import CepticClient, client_settings


# FIXTURES
@pytest.fixture(scope="module")
def locations():
    # location of tests (current dir)
    class _RealObject(object):
        def __init__(self):
            self.test_dir = os.path.join(os.path.realpath(
                os.path.join(os.getcwd(), os.path.dirname(__file__))))
            self.server_certs = os.path.join(self.test_dir, "server_certs")
            self.client_certs = os.path.join(self.test_dir, "client_certs")
            self.certfile = os.path.join(self.client_certs, "cert_client.pem")
            self.keyfile = os.path.join(self.client_certs, "key_client.pem")
            self.cafile = os.path.join(self.client_certs, "cert_server.pem")

    return _RealObject()
# END FIXTURES


# TESTS:
def test_client_creation_with_all_files(locations):
    _client_settings = client_settings()
    CepticClient(_client_settings, locations.certfile, locations.keyfile, locations.cafile)


def test_client_creation_with_certfile_keyfile_only(locations):
    _client_settings = client_settings()
    CepticClient(_client_settings, locations.certfile, locations.keyfile)


def test_client_creation_no_files_use_system_certs(locations):
    _client_settings = client_settings()
    CepticClient(_client_settings)
# END TESTS
