import uuid
from time import sleep

from ceptic.common import CepticStatusCode, CommandType
from ceptic.stream import CepticRequest, CepticResponse, Timer, StreamException
from tests.helpers.cepticinitializers import create_unsecure_client, create_unsecure_server
from tests.helpers.fixtures import context


def test_command_unsecure_success(context):
    # Arrange
    # create server
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    endpoint = "/"

    def entry(request: CepticRequest):
        return CepticResponse(CepticStatusCode.OK)

    server.add_command(command)
    server.add_route(command, endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost{endpoint}")

    # Act
    server.start()
    response = client.connect(request)

    # Assert
    assert response.status == CepticStatusCode.OK
    assert len(response.body) == 0
    assert not response.exchange


def test_command_unsecure_1000_success(context):
    # Arrange
    # create server
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    endpoint = "/"

    def entry(request: CepticRequest):
        return CepticResponse(CepticStatusCode.OK)

    server.add_command(command)
    server.add_route(command, endpoint, entry)
    server.start()

    timer = Timer()
    connect_timer = Timer()
    timer.start()

    # Act & Assert
    for i in range(1000):
        try:
            request = CepticRequest(CommandType.GET, f"localhost{endpoint}")
            # connect_timer.update()
            response = client.connect(request)
            # connect_timer.stop()
            # print(f"Connection took {connect_timer.get_time_diff() * 1000} ms")
            assert response.status == CepticStatusCode.OK
            assert not response.exchange
        except StreamException as e:
            print(f"Error thrown on iteration: {i},{type(e)},{e}")
            raise
    timer.stop()
    print(f"Total ms elapsed: {timer.get_time_diff() * 1000} ms")


def test_command_unsecure_echo_body_success(context):
    # Arrange
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    endpoint = "/"

    expected_body = "Hello world!".encode()

    def entry(request: CepticRequest):
        return CepticResponse(CepticStatusCode.OK, body=request.body)

    server.add_command(command)
    server.add_route(command, endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost{endpoint}", body=expected_body)
    # Act
    server.start()
    response = client.connect(request)
    # Assert
    assert response.status == CepticStatusCode.OK
    assert response.body == expected_body
    assert not response.exchange

    assert request.content_length == len(expected_body)
    assert response.content_length == len(expected_body)


def test_command_unsecure_echo_variables_success(context):
    # Arrange
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    variable_name1 = "var1"
    variable_name2 = "var2"
    register_endpoint = f"<{variable_name1}>/<{variable_name2}>"
    expected_value1 = uuid.uuid4()
    expected_value2 = uuid.uuid4()
    endpoint = f"{expected_value1}/{expected_value2}"

    expected_body = f"{variable_name1} was {expected_value1}, {variable_name2} was {expected_value2}".encode()

    def entry(request: CepticRequest):
        string_result = f"{variable_name1} was {request.values[variable_name1]}, " \
                        f"{variable_name2} was {request.values[variable_name2]}"
        if request.stream.settings.verbose:
            print(f"Sending body: {string_result}")
        return CepticResponse(CepticStatusCode.OK, body=string_result.encode())

    server.add_command(command)
    server.add_route(command, register_endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost/{endpoint}", body=expected_body)
    # Act
    server.start()
    response = client.connect(request)
    # Assert
    print(f"errors: {response.errors}")
    print(f"body: {response.body}")
    assert response.status == CepticStatusCode.OK
    assert response.body == expected_body
    assert not response.exchange

    assert request.content_length == len(expected_body)
    assert response.content_length == len(expected_body)


def test_command_unsecure_echo_queryparams_success(context):
    # Arrange
    client = create_unsecure_client()
    server = create_unsecure_server(verbose=True)
    context.server = server

    command = CommandType.GET
    variable_name1 = "var1"
    variable_name2 = "var2"
    register_endpoint = "/"
    expected_value1 = uuid.uuid4()
    expected_value2 = uuid.uuid4()
    endpoint = f"/?{variable_name1}={expected_value1}&{variable_name2}={expected_value2}"

    expected_body = f"{variable_name1} was {expected_value1}, {variable_name2} was {expected_value2}".encode()

    def entry(request: CepticRequest):
        string_result = f"{variable_name1} was {request.queryparams[variable_name1]}, " \
                        f"{variable_name2} was {request.queryparams[variable_name2]}"
        if request.stream.settings.verbose:
            print(f"Sending body: {string_result}")
        return CepticResponse(CepticStatusCode.OK, body=string_result.encode())

    server.add_command(command)
    server.add_route(command, register_endpoint, entry)

    request = CepticRequest(CommandType.GET, f"localhost/{endpoint}", body=expected_body)
    # Act
    server.start()
    response = client.connect(request)
    # Assert
    print(f"errors: {response.errors}")
    print(f"body: {response.body}")
    assert response.status == CepticStatusCode.OK
    assert response.body == expected_body
    assert not response.exchange

    assert request.content_length == len(expected_body)
    assert response.content_length == len(expected_body)
