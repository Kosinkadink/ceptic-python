import pytest
import threading
from sys import version_info

if version_info < (3, 0):  # if running python 2
    from Queue import Queue
else:
    from queue import Queue

from oldceptic.server import server_settings, begin_exchange
from oldceptic.client import client_settings
from oldceptic.common import CepticResponse, CepticException, CepticStatusCode


# TESTS:

@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_command(server_all_files, client_all_files):
    _here = test_get_command
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        response = client.connect_url("localhost:9000", "get")
        # check that status was OK and body was "no body"
        assert response.status == 200
        assert response.body == "no body"


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_echo_body(server_all_files, client_all_files):
    _here = test_get_echo_body
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        # include a body smaller than frame_max_size
        body = "HELLOTHERE"
        response = client.connect_url("localhost:9000", "get", body=body)
        # check that status was OK and body was "no body"
        assert response.status == CepticStatusCode.OK
        assert response.body == body


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_echo_body_multiple_frames(server_all_files, client_all_files):
    _here = test_get_echo_body_multiple_frames
    # init server and client; frame_max_size is set below size of body to force
    # multiple frames to be sent to transfer full data
    with server_all_files(settings=server_settings(verbose=True, frame_max_size=1000)) as app:
        _here.server = app
        client = client_all_files(settings=client_settings(frame_max_size=1000))

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        body = "HELLOTHERE"*100
        response = client.connect_url("localhost:9000", "get", body=body)
        # check that status was OK and body was "no body"
        assert response.status == CepticStatusCode.OK
        assert response.body == body


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_echo_body_encoding(server_all_files, client_all_files):
    _here = test_get_echo_body_encoding
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

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
            if response.status != CepticStatusCode.OK:
                pytest.fail("{} != {} for encoding: {}".format(response.status, CepticStatusCode.OK, encoding))
            if response.body != body:
                pytest.fail("{} != {} for encoding: {}".format(response.body, body, encoding))


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_echo_body_encoding_invalid(server_all_files, client_all_files):
    _here = test_get_echo_body_encoding_invalid
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # encodings to test (invalid on purpose)
        encodings = ["0gzip", "gz0ip,base64", "gzip,0base64"]
        # make request to server
        for encoding in encodings:
            headers = {"Encoding": encoding}
            # include a body smaller than frame_max_size
            body = "HELLOTHERE"
            with pytest.raises(CepticException):
                client.connect_url("localhost:9000", "get", headers, body=body)


@pytest.mark.usefixtures("server_certfile_keyfile_only", "client_cafile_only")
def test_get_only_server_related_files(server_certfile_keyfile_only, client_cafile_only):
    _here = test_get_only_server_related_files
    # init server and client
    with server_certfile_keyfile_only(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_cafile_only()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        response = client.connect_url("localhost:9000", "get")
        # check that status was OK and body was "no body"
        assert response.status == CepticStatusCode.OK
        assert response.body == "no body"


@pytest.mark.usefixtures("server_certfile_keyfile_only", "client_no_files")
def test_get_client_does_not_recognize_server_certs(server_certfile_keyfile_only, client_no_files):
    _here = test_get_client_does_not_recognize_server_certs
    # init server and client
    with server_certfile_keyfile_only(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_no_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        with pytest.raises(CepticException):
            client.connect_url("localhost:9000", "get")


@pytest.mark.usefixtures("server_not_secure", "client_not_secure")
def test_get_not_secure(server_not_secure, client_not_secure):
    _here = test_get_not_secure
    # init server and client
    with server_not_secure(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_not_secure()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        response = client.connect_url("localhost:9000", "get")
        # check that status was OK and body was "no body"
        assert response.status == CepticStatusCode.OK
        assert response.body == "no body"


@pytest.mark.usefixtures("client_all_files")
def test_get_server_not_found(client_all_files):
    _here = test_get_server_not_found
    # init client
    client = client_all_files()
    # make request to server
    with pytest.raises(CepticException):
        client.connect_url("localhost:9000", "get")


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_multiple_requests_series(server_all_files, client_all_files):
    _here = test_get_multiple_requests_series
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        for i in range(0, 10):  # send requests in series
            response = client.connect_url("localhost:9000/", "get")
            # check that status was OK and body was "no body"
            assert response.status == CepticStatusCode.OK
            assert response.body == "no body"


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_get_multiple_requests_parallel(server_all_files, client_all_files):
    _here = test_get_multiple_requests_parallel
    # init server and client
    with server_all_files(
            settings=server_settings(verbose=False, request_queue_size=100, stream_timeout=5)) as app:
        _here.server = app
        client = client_all_files(settings=client_settings(stream_timeout=5))

        # add test get command
        @app.route("/", "get")
        def get_command_test_route(request):
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server
        q = Queue()

        def make_request_thread(q_thread, client_thread, url, command, local_headers, body=None):
            local_response = client_thread.connect_url(url, command, local_headers, body)
            q_thread.put(local_response)

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
            assert response.status == CepticStatusCode.OK
            assert response.body == "no body"
            q.task_done()
            total_checked += 1
        print("Total Checked: {}".format(total_checked))


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_post_command(server_all_files, client_all_files):
    _here = test_post_command
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "post")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        response = client.connect_url("localhost:9000/", "post", body=body)
        # check that status was OK and body was equal to body
        assert response.status == CepticStatusCode.OK
        assert response.body == body


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_update_command(server_all_files, client_all_files):
    _here = test_update_command
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "update")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        response = client.connect_url("localhost:9000/", "update", body=body)
        # check that status was OK and body was equal to body
        assert response.status == CepticStatusCode.OK
        assert response.body == body


@pytest.mark.usefixtures("server_all_files", "client_all_files")
def test_delete_command(server_all_files, client_all_files):
    _here = test_delete_command
    # init server and client
    with server_all_files(settings=server_settings(verbose=True)) as app:
        _here.server = app
        client = client_all_files()

        # add test get command
        @app.route("/", "delete")
        def get_command_test_route(request):
            print("inside get_command_test_route")
            if request.body is not None:
                return CepticStatusCode.OK, request.body
            return CepticStatusCode.OK, "no body"

        # run server
        app.start()
        # make request to server with body
        body = "HELLOTHERE"
        response = client.connect_url("localhost:9000/", "delete", body=body)
        # check that status was OK and body was equal to body
        assert response.status == CepticStatusCode.OK
        assert response.body == body

# END TESTS


# set up/teardown for each function
def setup_function(function):
    function.server = None


def teardown_function(function):
    if function.server is not None:
        if not function.server.is_stopped():
            function.server.stop()
# done setup/teardown for each function
