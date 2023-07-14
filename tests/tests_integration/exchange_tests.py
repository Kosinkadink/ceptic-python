from time import sleep

import pytest

from ceptic.client import CepticClient
from ceptic.common import CommandType, CepticStatusCode
from ceptic.security import SecuritySettings
from ceptic.stream import CepticRequest, CepticResponse, Timer, StreamException, StreamClosedException
from tests.helpers.cepticinitializers import create_unsecure_client, create_unsecure_server
from tests.helpers.fixtures import context


def test_exchange_unsecure_success(context):
    # Arrange
    # create server
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    endpoint = "/"

    def entry(r: CepticRequest):
        stream = r.begin_exchange()
        if not stream:
            return CepticResponse(CepticStatusCode.UNEXPECTED_END)
        try:
            return CepticResponse(CepticStatusCode.EXCHANGE_END)
        except StreamException as e:
            if stream.settings.verbose:
                print(f"StreamException in Endpoint: {type(e)},{str(e)}")
            return CepticResponse(CepticStatusCode.UNEXPECTED_END)

    server.add_command(command)
    server.add_route(command, endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost{endpoint}")
    request.exchange = True

    # Act & Assert
    server.start()
    response = client.connect(request)
    assert response.status == CepticStatusCode.EXCHANGE_START
    assert response.exchange is True
    assert response.stream is not None

    stream = response.stream
    data = stream.read(200)
    assert data.is_response() is True
    response = data.response
    assert response.status == CepticStatusCode.EXCHANGE_END
    # sleep a little to make sure close frame is received by client before checking if stream is stopped
    sleep(0.05)
    assert stream.is_stopped() is True
    with pytest.raises(StreamClosedException) as exc_info:
        stream.read(200)


def test_exchange_unsecure_echo1000_success(context):
    # Arrange
    # create server
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    endpoint = "/"

    def entry(r: CepticRequest):
        stream = r.begin_exchange()
        if not stream:
            return CepticResponse(CepticStatusCode.UNEXPECTED_END)
        try:
            while True:
                data = stream.read(1000)
                if not data.is_data():
                    break
                if stream.settings.verbose:
                    print(f"Received data: {data.data.decode()}")
                stream.send(data.data)
            return CepticResponse(CepticStatusCode.EXCHANGE_END)
        except StreamException as e:
            if stream.settings.verbose:
                print(f"StreamException in Endpoint: {type(e)},{str(e)}")
            return CepticResponse(CepticStatusCode.UNEXPECTED_END)

    server.add_command(command)
    server.add_route(command, endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost{endpoint}")
    request.exchange = True

    # Act & Assert
    server.start()
    response = client.connect(request)
    assert response.status == CepticStatusCode.EXCHANGE_START
    assert response.exchange is True
    assert response.stream is not None
    assert response.stream.is_stopped() is False

    stream = response.stream

    timer = Timer()
    timer.start()
    exchange_count = 1000
    for i in range(0, exchange_count):
        expected_data = f"echo{i}".encode()
        stream.send(expected_data)
        data = stream.read(1000)
        assert data.is_data() is True
        assert data.data == expected_data
    timer.stop()
    print(f"{exchange_count} exchanges took {timer.get_time_diff()*1000} ms")

    stream.send_response(CepticResponse(CepticStatusCode.OK))
    last_data = stream.read(1000)
    assert last_data.is_response() is True
    assert last_data.response.status == CepticStatusCode.EXCHANGE_END
    # sleep a little to make sure close frame is received by client before checking if stream is stopped
    sleep(0.05)
    assert stream.is_stopped() is True
    with pytest.raises(StreamClosedException) as exc_info:
        stream.read(200)


# def test_exchange():
#     client = CepticClient(security=SecuritySettings.client_unsecure())
#     request = CepticRequest(command="get", url="localhost/exchange")
#     request.exchange = True
#
#     response = client.connect(request)
#     print(f"Request successful!\n{response}")
#     if response.exchange:
#         stream = response.stream
#         has_received_response = False
#         timer = Timer()
#         timer.start()
#         for i in range(10000):
#             string_data = f"echo{i}"
#             stream.send(string_data.encode())
#             data = stream.read(100)
#             if data.is_response():
#                 has_received_response = True
#                 print(f"Received response, end of exchange!\n{data.response}")
#                 break
#             if not data.data:
#                 print(f"Received None when expecting {string_data}")
#             # if i % 500 == 0:
#             #     print(f"Received echo: {data.decode()}")
#         timer.stop()
#         print(f"Time: {timer.get_time_diff()}")
#         if not has_received_response:
#             stream.send("exit".encode())
#             data = stream.read(100)
#             if data.is_response():
#                 has_received_response = True
#                 print(f"Received response after sending exit; end of exchange!\n{data.response}")
#         stream.send_close()
#
#     client.stop()
