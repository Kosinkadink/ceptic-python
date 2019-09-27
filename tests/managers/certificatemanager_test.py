import os
import pytest
from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.managers.certificatemanager import CertificateManager,CertificateManagerException,create_ssl_config

# TESTS:
def test_client_generage_context_all_files():
    _here = test_client_generage_context_all_files
    certfile=os.path.join(_here.client_certs,"cert_client.pem")
    keyfile=os.path.join(_here.client_certs,"key_client.pem")
    cafile=os.path.join(_here.client_certs,"cert_server.pem")
    config = create_ssl_config(certfile=certfile,keyfile=keyfile,cafile=cafile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()

def test_client_generate_context_certfile_keyfile_only():
    _here = test_client_generate_context_certfile_keyfile_only
    certfile=os.path.join(_here.client_certs,"cert_client.pem")
    keyfile=os.path.join(_here.client_certs,"key_client.pem")
    config = create_ssl_config(certfile=certfile,keyfile=keyfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()

def test_client_generage_context_no_files():
    _here = test_client_generage_context_no_files
    manager = CertificateManager.client()
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()

def test_client_generage_context_not_secure():
    _here = test_client_generage_context_not_secure
    config = create_ssl_config(secure=False)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()

def test_client_generate_context_certfile_only_raises_exception():
    _here = test_client_generate_context_certfile_only_raises_exception
    certfile=os.path.join(_here.client_certs,"cert_client.pem")
    config = create_ssl_config(certfile=certfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()

def test_client_generate_context_keyfile_only_raises_exception():
    _here = test_client_generate_context_keyfile_only_raises_exception
    keyfile=os.path.join(_here.client_certs,"key_client.pem")
    config = create_ssl_config(keyfile=keyfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()

# END TESTS


# TEST SETUP
def setup_function(function):
    # location of tests (current dir)
    function.test_dir = os.path.join(os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))))
    function.server_certs = os.path.join(function.test_dir,"../server_certs")
    function.client_certs = os.path.join(function.test_dir,"../client_certs")

def teardown_function(function):
    pass

def setup_module(module):
    pass

def teardown_module(module):
    pass
# END TEST SETUP

