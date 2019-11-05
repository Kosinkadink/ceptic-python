import os
import pytest
import contextlib
import threading
from time import sleep
from sys import version_info

if version_info < (3, 0):  # if running python 2
    from Queue import Queue
    from testingfixtures import add_surrounding_dir_to_path

    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()
else:
    from queue import Queue

from ceptic.server import CepticServer, CepticServerNew, create_server_settings
from ceptic.client import CepticClient, CepticClientNew, create_client_settings
from ceptic.common import CepticResponse


# FIXTURES:
@pytest.fixture(scope="module")
def locations():
    # location of tests (current dir)
    class _real_object(object):
        def __init__(self):
            self.test_dir = os.path.join(os.path.realpath(
                os.path.join(os.getcwd(), os.path.dirname(__file__))))
            self.server_certs = os.path.join(self.test_dir, "server_certs")
            self.s_certfile = os.path.join(self.server_certs, "cert_server.pem")
            self.s_keyfile = os.path.join(self.server_certs, "key_server.pem")
            self.s_cafile = os.path.join(self.server_certs, "cert_client.pem")
            self.client_certs = os.path.join(self.test_dir, "client_certs")
            self.c_certfile = os.path.join(self.client_certs, "cert_client.pem")
            self.c_keyfile = os.path.join(self.client_certs, "key_client.pem")
            self.c_cafile = os.path.join(self.client_certs, "cert_server.pem")

    return _real_object()


@pytest.fixture(scope="function")
def server_all_files(locations):
    @contextlib.contextmanager
    def _real_func(settings=None):
        print("server _real_func setup...")
        if settings is None:
            settings = create_server_settings()
        app = CepticServer(settings, locations.s_certfile, locations.s_keyfile, locations.s_cafile)
        yield app
        # cleanup
        if not app.is_stopped():
            print("cleaning up...")
            app.stop()
            while not app.is_stopped():
                sleep(0.05)

    return _real_func


@pytest.fixture(scope="function")
def server_certfile_keyfile_only(locations):
    @contextlib.contextmanager
    def _real_func(settings=None):
        if settings is None:
            settings = create_server_settings()
        app = CepticServer(settings, locations.s_certfile, locations.s_keyfile)
        yield app
        # cleanup
        if not app.is_stopped():
            app.stop()
            while not app.is_stopped():
                sleep(0.05)

    return _real_func


@pytest.fixture(scope="function")
def server_not_secure():
    @contextlib.contextmanager
    def _real_func(settings=None):
        if settings is None:
            settings = create_server_settings()
        app = CepticServer(settings, secure=False)
        yield app
        # cleanup
        if not app.is_stopped():
            app.stop()
            while not app.is_stopped():
                sleep(0.05)

    return _real_func


@pytest.fixture(scope="function")
def client_all_files(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings, locations.c_certfile, locations.c_keyfile, locations.c_cafile,
                            check_hostname=check_hostname)

    return _real_func


@pytest.fixture(scope="function")
def client_certfile_keyfile_only(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings, locations.c_certfile, locations.c_keyfile, check_hostname=check_hostname)

    return _real_func


@pytest.fixture(scope="function")
def client_cafile_only(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings, cafile=locations.c_cafile, check_hostname=check_hostname)

    return _real_func


@pytest.fixture(scope="function")
def client_no_files(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings, check_hostname=check_hostname)

    return _real_func


@pytest.fixture(scope="function")
def client_not_secure(locations):
    def _real_func(settings=None, check_hostname=False):
        if settings is None:
            settings = create_client_settings()
        return CepticClient(settings, check_hostname=check_hostname, secure=False)

    return _real_func


# END FIXTURES


# TESTS:
def test_get(server_all_files, client_all_files):
    _here = test_get
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        headers = dict()
        response = client.connect_url("localhost:9000", "get", headers)
        # check that status was OK and msg was "no body"
        assert response.status == 200
        assert response.msg == "no body"


def test_get_only_server_related_files(server_certfile_keyfile_only, client_cafile_only):
    _here = test_get_only_server_related_files
    # init server and client
    with server_certfile_keyfile_only(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_cafile_only()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        headers = dict()
        response = client.connect_url("localhost:9000", "get", headers)
        # check that status was OK and msg was "no body"
        assert response.status == 200
        assert response.msg == "no body"


def test_get_client_does_not_recognize_server_certs(server_certfile_keyfile_only, client_no_files):
    _here = test_get_client_does_not_recognize_server_certs
    # init server and client
    with server_certfile_keyfile_only(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_no_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        headers = dict()
        response = client.connect_url("localhost:9000", "get", headers)
        # check that status was 498 (error wrapping socket with ssl)
        assert response.status == 498


def test_get_not_secure(server_not_secure, client_not_secure):
    _here = test_get_not_secure
    # init server and client
    with server_not_secure(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_not_secure()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        headers = dict()
        response = client.connect_url("localhost:9000", "get", headers)
        # check that status was OK and msg was "no body"
        assert response.status == 200
        assert response.msg == "no body"


def test_get_server_not_found(client_all_files):
    _here = test_get
    # init client
    client = client_all_files()
    # make request to server
    headers = dict()
    response = client.connect_url("localhost:9000", "get", headers)
    # check that status was 494 - server at url not found
    assert response.status == 494


def test_get_multiple_requests_series(server_all_files, client_all_files):
    _here = test_get_multiple_requests_series
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        headers = dict()
        for i in range(0, 10):  # send requests in series
            response = client.connect_url("localhost:9000/", "get", headers)
            # check that status was OK and msg was "no body"
            assert response.status == 200
            assert response.msg == "no body"


def test_get_multiple_requests_parallel(server_all_files, client_all_files):
    _here = test_get_multiple_requests_parallel
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=False, request_queue_size=100)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server
        q = Queue()

        def make_request_thread(qThread, clientThread, url, command, headers, body=None):
            response = clientThread.connect_url(url, command, headers, body)
            qThread.put(response)

        headers = dict()
        threads = []
        thread_count = 100
        for i in range(0, thread_count):  # send request in parallel
            new_thread = threading.Thread(target=make_request_thread,
                                          args=(q, client, "localhost:9000/", "get", headers))
            threads.append(new_thread)
            new_thread.start()
        for thread in threads:
            thread.join()
        # check that each response was a success
        assert q.qsize() == thread_count
        while not q.empty():
            # check that status was OK and msg was "no body"
            response = q.get()
            assert response.status == 200
            assert response.msg == "no body"
            q.task_done()


def test_post(server_all_files, client_all_files):
    _here = test_post
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "post")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        headers = {"Content-Length": len(body)}
        response = client.connect_url("localhost:9000/", "post", headers, body)
        # check that status was OK and msg was equal to body 
        assert response.status == 200
        assert response.msg == body


def test_update(server_all_files, client_all_files):
    _here = test_update
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "update")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        headers = {"Content-Length": len(body)}
        response = client.connect_url("localhost:9000/", "update", headers, body)
        # check that status was OK and msg was equal to body 
        assert response.status == 200
        assert response.msg == body


def test_delete(server_all_files, client_all_files):
    _here = test_delete
    # init server and client
    with server_all_files(settings=create_server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "delete")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return 200, request.body
            return 200, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        headers = {"Content-Length": len(body)}
        response = client.connect_url("localhost:9000/", "delete", headers, body)
        # check that status was OK and msg was equal to body 
        assert response.status == 200
        assert response.msg == body


def test_stream():
    pass


def test_streamget():
    pass


def test_streampost():
    pass


# END TESTS

# set up/teardown for each function
def setup_function(function):
    function.server = None


def teardown_function(function):
    if function.server is not None:
        if not function.server.is_stopped():
            function.server.stop()
            while not function.server.is_stopped():
                sleep(0.05)


# done setup/teardown for each function


if __name__ == "__main__":
    client_settings = create_client_settings()
    client = CepticClientNew(settings=client_settings, secure=False)
    server_settings = create_server_settings(port=9000, verbose=True)
    server = CepticServerNew(settings=server_settings, secure=False)
    # start server
    server.start()
    headers = dict()
    client.connect_url("localhost:9000/", "get", headers=headers)
    server.stop()
    while not server.is_stopped():
        sleep(0.1)
