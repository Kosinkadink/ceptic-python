import pytest
import os

# FIXTURES:
@pytest.fixture(scope="module")
def locations():
    # location of tests (current dir)
    class _RealObject(object):
        def __init__(self):
            self.test_dir = os.path.join(os.path.join(os.path.realpath(
                os.path.join(os.getcwd(), os.path.dirname(__file__)))), "../")
            self.server_certs = os.path.join(self.test_dir, "server_certs")
            self.s_certfile = os.path.join(self.server_certs, "cert_server.pem")
            self.s_keyfile = os.path.join(self.server_certs, "key_server.pem")
            self.s_cafile = os.path.join(self.server_certs, "cert_client.pem")
            self.client_certs = os.path.join(self.test_dir, "client_certs")
            self.c_certfile = os.path.join(self.client_certs, "cert_client.pem")
            self.c_keyfile = os.path.join(self.client_certs, "key_client.pem")
            self.c_cafile = os.path.join(self.client_certs, "cert_server.pem")
    return _RealObject()