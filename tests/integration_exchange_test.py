import pytest
import threading
from sys import version_info

if version_info < (3, 0):  # if running python 2
    from Queue import Queue
else:
    from queue import Queue

from ceptic.server import server_settings, begin_exchange
from ceptic.client import client_settings
from ceptic.common import CepticResponse, CepticException, CepticStatusCode


# TESTS:

@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_exchange(server_all_files, client_all_files):
    _here = test_exchange
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_exchange_test_route(request):
            print("inside get_command_exchange_test_route")
            stream = begin_exchange(request)
            for i in range(100):
                stream.send_data("{}".format(i))
            return CepticStatusCode.OK

        # run server
        app.start()
        # make request to server
        response = client.connect_url("localhost:9000/", "get")
        assert not response.stream.is_stopped()
        # get data from stream and validate it
        for n in range(100):
            data = response.stream.get_data()
            assert data is not None
            assert not isinstance(data, CepticResponse)
            assert int(data) == n
        # expect next data to be type CepticResponse
        final_response = response.stream.get_data()
        assert final_response is not None
        assert isinstance(final_response, CepticResponse)
        assert final_response.status == CepticStatusCode.OK


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_exchange_echo(server_all_files, client_all_files):
    _here = test_exchange_echo
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_exchange_echo_test_route(request):
            print("inside get_command_exchange_echo_test_route")
            stream = begin_exchange(request)
            for i in range(100):
                data = stream.get_data()
                if isinstance(data, CepticResponse):
                    return CepticStatusCode.NO_CONTENT
                stream.send_data("{}".format(data))
            return CepticStatusCode.OK

        # run server
        app.start()
        # make request to server
        response = client.connect_url("localhost:9000/", "get")
        assert not response.stream.is_stopped()
        # get data from stream and validate it
        for n in range(100):
            message = "{}".format(n)
            response.stream.send_data(message)
            data = response.stream.get_data()
            assert data is not None
            assert not isinstance(data, CepticResponse)
            assert message == data
        # expect next data to be type CepticResponse
        final_response = response.stream.get_data()
        assert final_response is not None
        assert isinstance(final_response, CepticResponse)
        assert final_response.status == CepticStatusCode.OK


# END TESTS

# set up/teardown for each function
def setup_function(function):
    function.server = None


def teardown_function(function):
    if function.server is not None:
        if not function.server.is_stopped():
            function.server.stop()
# done setup/teardown for each function