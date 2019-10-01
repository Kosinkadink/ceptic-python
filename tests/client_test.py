import os
import pytest
from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.client import CepticClient, create_client_settings


# FIXTURES
@pytest.fixture(scope="module")
def locations():
    # location of tests (current dir)
    class _real_object(object):
        def __init__(self):
            self.test_dir = os.path.join(os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))))
            self.server_certs = os.path.join(self.test_dir,"server_certs")
            self.client_certs = os.path.join(self.test_dir,"client_certs")
            self.certfile=os.path.join(self.client_certs,"cert_client.pem")
            self.keyfile=os.path.join(self.client_certs,"key_client.pem")
            self.cafile=os.path.join(self.client_certs,"cert_server.pem")
    return _real_object()
# END FIXTURES


# TESTS:
def test_client_creation_with_all_files(locations):
    client_settings = create_client_settings()
    client = CepticClient(client_settings,locations.certfile,locations.keyfile,locations.cafile)

def test_client_creation_with_certfile_keyfile_only(locations):
    client_settings = create_client_settings()
    client = CepticClient(client_settings,locations.certfile,locations.keyfile)

def test_client_creation_no_files_use_system_certs(locations):
    client_settings = create_client_settings()
    client = CepticClient(client_settings)
# END TESTS
