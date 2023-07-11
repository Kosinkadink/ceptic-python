from time import sleep
from typing import Union

import pytest

from ceptic.server import CepticServer
from ceptic.stream import Timer


class TestContext(object):
    def __init__(self):
        self.server: Union[CepticServer, None] = None


@pytest.fixture(scope="function")
def context():
    tc = TestContext()
    yield tc
    if tc.server and not tc.server.is_stopped():
        tc.server.stop()
        timer = Timer()
        timer.start()
        while not tc.server.is_stopped() or timer.get_time_current() < 1.0:
            sleep(0.001)
        print("server stopped by fixture!")
