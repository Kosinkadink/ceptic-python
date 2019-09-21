from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.client import CepticClient, create_client_settings
from ceptic.managers.certificatemanager import create_ssl_config
import os


# TESTS:
def test_client_creation_with_certs():
    _here = test_client_creation_with_certs
    ssl_settings = create_ssl_config(
        certfile=os.path.join(_here.client_certs,"cert_client.pem"),
        keyfile=os.path.join(_here.client_certs,"key_client.pem"),
        cafile=os.path.join(_here.client_certs,"cert_server.pem")
        )
    client_settings = create_client_settings()
    client = CepticClient(client_settings,ssl_settings)

def test_client_creation_with_certs_no_verify():
    _here = test_client_creation_with_certs_no_verify
    ssl_settings = create_ssl_config(
        certfile=os.path.join(_here.client_certs,"cert_client.pem"),
        keyfile=os.path.join(_here.client_certs,"key_client.pem")
        )
    client_settings = create_client_settings()
    client = CepticClient(client_settings,ssl_settings)

def test_client_creation_no_certs():
    _here = test_client_creation_no_certs
    client_settings = create_client_settings()
    client = CepticClient(client_settings)
# END TESTS


# TEST SETUP
def setup_function(function):
    # location of tests (current dir)
    function.test_dir = os.path.join(os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))))
    function.server_certs = os.path.join(function.test_dir,"server_certs")
    function.client_certs = os.path.join(function.test_dir,"client_certs")

def teardown_function(function):
    pass

def setup_module(module):
    pass

def teardown_module(module):
    pass
# END TEST SETUP
