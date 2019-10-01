import os
from time import sleep
from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.server import CepticServer, create_server_settings
from ceptic.client import CepticClient, create_client_settings
from ceptic.common import CepticResponse

# FIXTURES:
def server_all_files():
    def _real_func(cert_location,settings=None):
        certfile=os.path.join(cert_location,"cert_server.pem")
        keyfile=os.path.join(cert_location,"key_server.pem")
        cafile=os.path.join(cert_location,"cert_client.pem")
        if settings is None:
            settings = create_server_settings()
        return CepticServer(settings,certfile,keyfile,cafile)
    return _real_func

def server_certfile_keyfile_only():
    def _real_func(cert_location,settings=None):
        certfile=os.path.join(cert_location,"cert_server.pem")
        keyfile=os.path.join(cert_location,"key_server.pem")
        if settings is None:
            settings = create_server_settings()
        return CepticServer(settings,certfile,keyfile,cafile)
    return _real_func

def server_not_secure():
    def _real_func(cert_location,settings=None):
        if settings is None:
            settings = create_server_settings()
        return CepticServer(settings,secure=False)
    return _real_func

def client_all_files():
    def _real_func(cert_location,settings=None,check_hostname=False):
        certfile=os.path.join(cert_location,"cert_client.pem")
        keyfile=os.path.join(cert_location,"key_client.pem")
        cafile=os.path.join(cert_location,"cert_server.pem")
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings,certfile,keyfile,cafile,check_hostname=check_hostname)
    return _real_func

def client_certfile_keyfile_only():
    def _real_func(cert_location,settings=None,check_hostname=False):
        certfile=os.path.join(cert_location,"cert_client.pem")
        keyfile=os.path.join(cert_location,"key_client.pem")
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings,certfile,keyfile,check_hostname=check_hostname)
    return _real_func

def client_cafile_only():
    def _real_func(cert_location,settings=None,check_hostname=False):
        cafile=os.path.join(cert_location,"cert_server.pem")
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings,cafile=cafile,check_hostname=check_hostname)
    return _real_func

def client_no_files():
    def _real_func(cert_location,settings=None,check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings,check_hostname=check_hostname)
    return _real_func

def client_not_secure():
    def _real_func(cert_location,settings=None,check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings,check_hostname=check_hostname,secure=False)
    return _real_func

# END FIXTURES


# TESTS:
def test_get():
    _here = test_get
    # init server
    certfile=os.path.join(_here.server_certs,"cert_server.pem")
    keyfile=os.path.join(_here.server_certs,"key_server.pem")
    cafile=os.path.join(_here.server_certs,"cert_client.pem")
    server_settings = create_server_settings()
    _here.server = CepticServer(server_settings,certfile,keyfile,cafile)
    # add test get command
    @_here.server.route("/","get")
    def get_command_test_route(request):
        return CepticResponse(200, "testgetsuccess")
    # init client


def test_post():
    pass

def test_update():
    pass

def test_delete():
    pass

def test_stream():
    pass

def test_streamget():
    pass

def test_streampost():
    pass
# END TESTS


# TEST SETUP
def setup_function(function):
    # location of tests (current dir)
    function.test_dir = os.path.join(os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))))
    # cert locations
    function.server_certs = os.path.join(function.test_dir,"server_certs")
    function.client_certs = os.path.join(function.test_dir,"client_certs")
    # client/server placeholders
    function.server = None
    function.client = None

def teardown_function(function):
    # clean up server and client, if exist
    if function.server is not None:
        function.server.stop()
        sleep(0.1)

def setup_module(module):
    pass

def teardown_module(module):
    pass
# END TEST SETUP