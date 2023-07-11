import pytest

from ceptic.client import CepticClient
from ceptic.security import SecuritySettings
from ceptic.stream import CepticRequest, CepticResponse, Timer


def test_exchange():
    client = CepticClient(security=SecuritySettings.client_unsecure())
    request = CepticRequest(command="get", url="localhost/exchange")
    request.exchange = True

    response = client.connect(request)
    print(f"Request successful!\n{response}")
    if response.exchange:
        stream = response.stream
        has_received_response = False
        timer = Timer()
        timer.start()
        for i in range(10000):
            string_data = f"echo{i}"
            stream.send(string_data.encode())
            data = stream.read(100)
            if data.is_response():
                has_received_response = True
                print(f"Received response, end of exchange!\n{data.response}")
                break
            if not data.data:
                print(f"Received None when expecting {string_data}")
            # if i % 500 == 0:
            #     print(f"Received echo: {data.decode()}")
        timer.stop()
        print(f"Time: {timer.get_time_diff()}")
        if not has_received_response:
            stream.send("exit".encode())
            data = stream.read(100)
            if data.is_response():
                has_received_response = True
                print(f"Received response after sending exit; end of exchange!\n{data.response}")
        stream.send_close()

    client.stop()
