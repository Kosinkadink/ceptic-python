import os
import pytest
from ceptic.server import CepticServer, create_server_settings, basic_server_command


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
            self.certfile = os.path.join(self.server_certs, "cert_server.pem")
            self.keyfile = os.path.join(self.server_certs, "key_server.pem")
            self.cafile = os.path.join(self.server_certs, "cert_client.pem")

    return _RealObject()
# END FIXTURES


# TESTS:
def test_server_creation_with_certs(locations):
    server_settings = create_server_settings()
    app = CepticServer(server_settings, locations.certfile, locations.keyfile, locations.cafile)
    app.start()
    app.stop()


def test_server_creation_with_certs_no_verify(locations):
    server_settings = create_server_settings()
    app = CepticServer(server_settings, locations.certfile, locations.keyfile)
    app.start()
    app.stop()


def test_server_creation_with_no_certs(locations):
    server_settings = create_server_settings()
    app = CepticServer(server_settings)
    app.start()
    app.stop()


def test_add_route(locations):
    server_settings = create_server_settings()
    app = CepticServer(server_settings)

    # create a route
    @app.route("/", "get")
    def sample_get_endpoint(request):
        return 200, 'OK'

    # check that route has been added
    command_func, handler, variable_dict, settings, settings_override = app.endpointManager.get_endpoint("get", "/")
    assert command_func is basic_server_command
    assert handler is sample_get_endpoint
    assert len(variable_dict) == 0
    assert settings_override is None


def test_add_route_with_variable(locations):
    server_settings = create_server_settings()
    app = CepticServer(server_settings)

    # create a route
    @app.route("/testing/<test_variable>", "get")
    def sample_get_endpoint(request, test_variable):
        return 200, 'OK: {}'.format(test_variable)

    # check that route has been added
    value = "test_value"
    command_func, handler, variable_dict, settings, settings_override = app.endpointManager.get_endpoint(
        "get", "/testing/{}".format(value))
    assert command_func is basic_server_command
    assert handler is sample_get_endpoint
    assert len(variable_dict) == 1
    assert variable_dict["test_variable"] == value
    assert settings_override is None

# END TESTS
