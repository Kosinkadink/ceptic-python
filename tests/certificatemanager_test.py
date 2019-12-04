import os
import pytest
from ceptic.certificatemanager import CertificateManager, CertificateManagerException, create_ssl_config


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
    return _RealObject()
# END FIXTURES


# TESTS:

# Client Tests
def test_client_generage_context_all_files(locations):
    certfile = os.path.join(locations.client_certs, "cert_client.pem")
    keyfile = os.path.join(locations.client_certs, "key_client.pem")
    cafile = os.path.join(locations.client_certs, "cert_server.pem")
    config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()


def test_client_generate_context_certfile_keyfile_only(locations):
    certfile = os.path.join(locations.client_certs, "cert_client.pem")
    keyfile = os.path.join(locations.client_certs, "key_client.pem")
    config = create_ssl_config(certfile=certfile, keyfile=keyfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()


def test_client_generage_context_no_files(locations):
    manager = CertificateManager.client()
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()


def test_client_generage_context_not_secure(locations):
    config = create_ssl_config(secure=False)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    manager.generate_context_tls()


def test_client_generate_context_certfile_only_raises_exception(locations):
    certfile = os.path.join(locations.client_certs, "cert_client.pem")
    config = create_ssl_config(certfile=certfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()


def test_client_generate_context_keyfile_only_raises_exception(locations):
    keyfile = os.path.join(locations.client_certs, "key_client.pem")
    config = create_ssl_config(keyfile=keyfile)
    manager = CertificateManager.client(config)
    assert manager.generate_context_tls == manager.generate_context_client
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()


# Server
def test_server_generate_context_all_files(locations):
    certfile = os.path.join(locations.server_certs, "cert_server.pem")
    keyfile = os.path.join(locations.server_certs, "key_server.pem")
    cafile = os.path.join(locations.server_certs, "cert_client.pem")
    config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile)
    manager = CertificateManager.server(config)
    assert manager.generate_context_tls == manager.generate_context_server
    manager.generate_context_tls()


def test_server_generate_context_certfile_keyfile_only(locations):
    certfile = os.path.join(locations.server_certs, "cert_server.pem")
    keyfile = os.path.join(locations.server_certs, "key_server.pem")
    config = create_ssl_config(certfile=certfile, keyfile=keyfile)
    manager = CertificateManager.server(config)
    assert manager.generate_context_tls == manager.generate_context_server
    manager.generate_context_tls()


def test_server_generage_context_no_files_raises_exception(locations):
    manager = CertificateManager.server()
    assert manager.generate_context_tls == manager.generate_context_server
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()


def test_server_generage_context_not_secure(locations):
    config = create_ssl_config(secure=False)
    manager = CertificateManager.server(config)
    assert manager.generate_context_tls == manager.generate_context_server
    manager.generate_context_tls()


def test_server_generate_context_certfile_only_raises_exception(locations):
    certfile = os.path.join(locations.server_certs, "cert_server.pem")
    config = create_ssl_config(certfile=certfile)
    manager = CertificateManager.server(config)
    assert manager.generate_context_tls == manager.generate_context_server
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()


def test_server_generate_context_keyfile_only_raises_exception(locations):
    keyfile = os.path.join(locations.server_certs, "key_server.pem")
    config = create_ssl_config(keyfile=keyfile)
    manager = CertificateManager.server(config)
    assert manager.generate_context_tls == manager.generate_context_server
    with pytest.raises(CertificateManagerException):
        manager.generate_context_tls()

# END TESTS
