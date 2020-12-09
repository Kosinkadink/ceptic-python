import pytest
import contextlib

from ceptic.server import CepticServer, server_settings


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def server_all_files(locations):
    @contextlib.contextmanager
    def _real_func(settings=None):
        if settings is None:
            settings = server_settings()
        app = CepticServer(settings, locations.s_certfile, locations.s_keyfile, locations.s_cafile)
        yield app
        # cleanup
        if not app.is_stopped():
            app.stop()
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def server_certfile_keyfile_only(locations):
    @contextlib.contextmanager
    def _real_func(settings=None):
        if settings is None:
            settings = server_settings()
        app = CepticServer(settings, locations.s_certfile, locations.s_keyfile)
        yield app
        # cleanup
        if not app.is_stopped():
            app.stop()
    return _real_func


@pytest.fixture(scope="function")
@pytest.mark.usefixtures("locations")
def server_not_secure():
    @contextlib.contextmanager
    def _real_func(settings=None):
        if settings is None:
            settings = server_settings()
        app = CepticServer(settings, secure=False)
        yield app
        # cleanup
        if not app.is_stopped():
            app.stop()
    return _real_func
