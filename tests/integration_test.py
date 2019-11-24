import os
import pytest
import contextlib
import threading
from time import sleep
from sys import version_info

if version_info < (3, 0):  # if running python 2
    from Queue import Queue
else:
    from queue import Queue

from ceptic.server import CepticServer, create_server_settings
from ceptic.client import CepticClient, create_client_settings
from ceptic.common import CepticResponse, CepticException


# FIXTURES:
@pytest.fixture(scope="module")
def locations():
    # location of tests (current dir)
    class _RealObject(object):
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

    return _RealObject()


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
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == "no body"


def test_get_echo_body(server_all_files, client_all_files):
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
        # include a body smaller than frame_max_size
        body = "HELLOTHERE"
        response = client.connect_url("localhost:9000", "get", headers, body=body)
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == body


def test_get_echo_body_multiple_frames(server_all_files, client_all_files):
    _here = test_get
    # init server and client; frame_max_size is set below size of body to force
    # multiple frames to be sent to transfer full data
    with server_all_files(settings=create_server_settings(verbose=True, frame_max_size=1000)) as app:
        _here.server = app
        client = client_all_files(settings=create_client_settings(frame_max_size=1000))

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
        body = "HELLOTHERE"*100
        response = client.connect_url("localhost:9000", "get", headers, body=body)
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == body


def test_get_echo_body_encoding(server_all_files, client_all_files):
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
        # encodings to test
        encodings = ["gzip", "base64", "gzip,base64"]
        # make request to server
        for encoding in encodings:
            headers = {"Encoding": encoding}
            # include a body smaller than frame_max_size
            body = "HELLOTHERE"
            response = client.connect_url("localhost:9000", "get", headers, body=body)
            # check that status was OK and body was "no body"
            if response.status != 200:
                pytest.fail("{} != 200 for encoding: {}".format(response.status, encoding))
            if response.body != body:
                pytest.fail("{} != {} for encoding: {}".format(response.body, body, encoding))


def test_get_echo_body_encoding_invalid(server_all_files, client_all_files):
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
        # encodings to test
        encodings = ["0gzip", "gz0ip,base64", "gzip,0base64"]
        # make request to server
        for encoding in encodings:
            headers = {"Encoding": encoding}
            # include a body smaller than frame_max_size
            body = "HELLOTHERE"
            with pytest.raises(CepticException):
                client.connect_url("localhost:9000", "get", headers, body=body)


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
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == "no body"


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
        with pytest.raises(CepticException):
            response = client.connect_url("localhost:9000", "get", headers)


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
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == "no body"


def test_get_server_not_found(client_all_files):
    _here = test_get
    # init client
    client = client_all_files()
    # make request to server
    headers = dict()
    with pytest.raises(CepticException):
        response = client.connect_url("localhost:9000", "get", headers)


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
            # check that status was OK and body was "no body"
            assert response.status == 200
            assert response.body == "no body"


def test_get_multiple_requests_parallel(server_all_files, client_all_files):
    _here = test_get_multiple_requests_parallel
    # init server and client
    with server_all_files(
            settings=create_server_settings(verbose=False, request_queue_size=100, stream_timeout=5)) as app:
        _here.server = app
        client = client_all_files(settings=create_client_settings(stream_timeout=5))

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

        def make_request_thread(q_thread, client_thread, url, command, headers, body=None):
            response = client_thread.connect_url(url, command, headers, body)
            q_thread.put(response)

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
        total_checked = 0
        while not q.empty():
            # check that status was OK and body was "no body"
            response = q.get()
            if response.errors:
                print("Errors: {}".format(response.errors))
            assert response.status == 200
            assert response.body == "no body"
            q.task_done()
            total_checked += 1
        print("Total Checked: {}".format(total_checked))


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
        # check that status was OK and body was equal to body
        assert response.status == 200
        assert response.body == body


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
        # check that status was OK and body was equal to body
        assert response.status == 200
        assert response.body == body


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
        # check that status was OK and body was equal to body
        assert response.status == 200
        assert response.body == body


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
