import os
from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.server import CepticServer, create_server_settings


# TESTS:
def test_server_creation_with_certs():
    _here = test_server_creation_with_certs
    certfile=os.path.join(_here.server_certs,"cert_server.pem")
    keyfile=os.path.join(_here.server_certs,"key_server.pem")
    cafile=os.path.join(_here.server_certs,"cert_client.pem")
    server_settings = create_server_settings()
    app = CepticServer(server_settings,certfile,keyfile,cafile)
    app.run()
    app.stop()

def test_server_creation_with_certs_no_verify():
    _here = test_server_creation_with_certs_no_verify
    certfile=os.path.join(_here.server_certs,"cert_server.pem")
    keyfile=os.path.join(_here.server_certs,"key_server.pem")
    server_settings = create_server_settings()
    app = CepticServer(server_settings,certfile,keyfile)
    app.run()
    app.stop()

def test_server_creation_with_no_certs():
    _here = test_server_creation_with_no_certs
    server_settings = create_server_settings()
    app = CepticServer(server_settings)
    app.run()
    app.stop()
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
