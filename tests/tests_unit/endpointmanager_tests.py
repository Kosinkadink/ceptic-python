from typing import List, Union

import pytest
import re
from contextlib import nullcontext as does_not_raise

from ceptic.common import CepticStatusCode
from ceptic.endpoint import EndpointManager, EndpointEntry, EndpointManagerException, EndpointValue
from ceptic.server import ServerSettings
from ceptic.stream import CepticResponse


BASIC_ENDPOINT_ENTRY: EndpointEntry = lambda request, values: CepticResponse(CepticStatusCode.OK)


# region Fixtures
@pytest.fixture(scope="module")
def manager():
    return EndpointManager(ServerSettings())
# endregion


# region Tests
def test_create_manager_success(manager):
    # Arrange, Act, Assert
    assert isinstance(manager, EndpointManager)


def test_add_command_success(manager):
    # Arrange
    command = "get"
    # Act
    manager.add_command(command)
    # Assert
    assert manager.get_command(command) is not None


def test_get_command_success(manager):
    # Arrange
    command = "get"
    manager.add_command(command)
    # Act
    entry = manager.get_command(command)
    # Assert
    assert entry is not None
    assert entry.command == command


def test_get_command_doesnotexist_isnull(manager):
    # Arrange
    manager.add_command("get")
    # Act
    entry = manager.get_command("post")
    # Assert
    assert entry is None


def test_remove_command_success(manager):
    # Arrange
    command = "get"
    manager.add_command(command)
    # Act
    entry = manager.remove_command(command)
    # Assert
    assert entry is not None
    assert entry.command == command


def test_remove_command_doesnotexist_isnull(manager):
    # Arrange, Act
    entry = manager.remove_command("get")
    # Assert
    assert entry is None


def test_add_endpoint_success(manager):
    # Arrange
    command = "get"
    manager.add_command(command)
    endpoint = "/"
    # Act, Assert
    with does_not_raise() as e:
        manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)


def test_add_endpoint_commanddoesnotexist_throws(manager):
    # Arrange
    command = "get"
    endpoint = "/"
    # Act, Assert
    with pytest.raises(EndpointManagerException) as exc_info:
        manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)


def test_add_endpoint_goodendpoints_noexceptions(manager):
    # Arrange
    command = "get"
    # endpoints can be a single dash
    endpoints: list[str] = ["/"]
    # endpoint can be composed of any alphanumerics as well as -.<>_/ characters
    # (but <> have to be enclosing something)
    good_var_start_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    good_var_chars = good_var_start_chars + "1234567890"
    good_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-._"
    for char in good_chars:
        endpoints.append(char)
        endpoints.append(f"{char}/test")
        endpoints.append(f"test/{char}")
    # endpoint can contain braces for variable portion of url; they have to enclose something
    endpoints.append("good/<braces>")
    endpoints.append("<braces>")
    endpoints.append("<good>/braces")
    # variables can start with alphabet and underscore, non-first characters can be alphanumerics and underscore
    for char in good_var_start_chars:
        endpoints.append(f"<{char}>")
        for other_char in good_var_chars:
            endpoints.append(f"<{char + other_char}>")
    # variable name can start with underscore
    endpoints.append("<_underscore>/in/variable/name")
    # multiple variables allowed separated by slashes
    endpoints.append("<multiple>/<variables>")
    # endpoint can start or end with multiple (or no) slashes
    endpoints.append("no_slashes_at_all")
    endpoints.append("/only_slash_at_start")
    endpoints.append("only_slash_at_end/")
    endpoints.append("/surrounding_slashes/")
    endpoints.append("////multiple_slashes/////////////////")

    # Act, Assert
    for endpoint in endpoints:
        # re-add command to make sure each endpoint is tested individually
        manager.add_command(command)
        with does_not_raise() as e:
            try:
                manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)
            except Exception:
                print(f"\nEndpoint: {endpoint}")
                raise
        manager.remove_command(command)


def test_add_endpoint_badendpoints_throws(manager):
    # Arrange
    command = "get"
    # endpoints cannot be blank
    endpoints: list[str] = [""]
    # non-alphanumeric or non -.<>_/ symbols are not allowed
    bad_chars = "!@#$%^&*()=+`~[}{]\\|;:\"', "
    for char in bad_chars:
        endpoints.append(char)
        endpoints.append(f"{char}/test")
        endpoints.append(f"test/{char}")
    # consecutive slahses in the middle are not allowed
    endpoints.append("bad//endpoint")
    endpoints.append("/bad/endpoint//2/")
    # braces cannot be across a slash
    endpoints.append("bad/<bra/ces>")
    # braces cannot have nothing in between
    endpoints.append("bad/<>/braces")
    # braces must close
    endpoints.append("unmatched/<braces")
    endpoints.append("unmatched/<braces>>")
    endpoints.append("unmatched/<braces>/other>")
    endpoints.append(">braces")
    endpoints.append("braces<")
    # braces cannot contain other braces
    endpoints.append("unmatched/<<braces>>")
    endpoints.append("unmatched/<b<race>s>")
    # braces cannot be placed directly adjacent to each other
    endpoints.append("multiple/<unslashed><braces>")
    # braces cannot be placed more than once between slashes
    endpoints.append("multiple/<braces>.<between>")
    endpoints.append("multiple/<braces>.<between>/slashes")
    endpoints.append("<bad>bad<braces>")
    # variable name in braces cannot start with a number
    endpoints.append("starts/<1withnumber>")
    # multiple variables cannot have the same name
    endpoints.append("<variable>/<variable>")

    for endpoint in endpoints:
        # re-add command to make sure each endpoint is tested individually
        manager.add_command(command)
        with pytest.raises(EndpointManagerException) as e:
            try:
                manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)
            except EndpointManagerException:
                raise
            else:
                print(f"\nEndpoint: {endpoint}")
        manager.remove_command(command)


def test_add_endpoint_equivalentexchange_throws(manager):
    # Arrange
    command = "get"
    endpoints: list[str] = []
    # add valid endpoints
    manager.add_command(command)
    manager.add_endpoint(command, "willalreadyexist", BASIC_ENDPOINT_ENTRY)
    manager.add_endpoint(command, "willalready/<exist>", BASIC_ENDPOINT_ENTRY)
    # endpoint cannot already exist; slash at beginning or end makes no difference
    endpoints.append("willalreadyexist")
    endpoints.append("/willalreadyexist")
    endpoints.append("willalreadyexist/")
    endpoints.append("///willalreadyexist/////")
    # equivalent variable format is also not allowed
    endpoints.append("willalready/<exist>")
    endpoints.append("willalready/<exist1>")

    # Act, Assert
    for endpoint in endpoints:
        with pytest.raises(EndpointManagerException) as e:
            try:
                manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)
            except EndpointManagerException:
                raise
            else:
                print(f"\nEndpoint: {endpoint}")


def test_get_endpoint_success(manager):
    # Arrange
    command = "get"
    endpoint = "/"
    manager.add_command(command)
    manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)
    # Act, Assert
    endpoint_value: Union[EndpointValue, None] = None
    with does_not_raise() as e:
        endpoint_value = manager.get_endpoint(command, endpoint)
    assert endpoint is not None
    # variable map should be empty
    assert len(endpoint_value.values) == 0
    # entry should be the same as put in
    assert endpoint_value.entry == BASIC_ENDPOINT_ENTRY


def test_get_endpoint_withvariables_success(manager):
    # Arrange
    command = "get"
    manager.add_command(command)
    regex = re.compile("@")
    templates = [
        "test/@",
        "@/@",
        "test/@/@",
        "test/@/other/@",
        "@/tests/variable0/@",
        "@/@/@/@/@",
        "@/@/@/@/@/test"
    ]
    # Act, Assert
    for template in templates:
        count = 0
        variable_map = dict()
        prepared = template
        query = template
        start_index = 0
        match = regex.search(template, pos=start_index)
        while match:
            start_index = match.end()
            name = f"variable{count}"
            value = f"value{count}"
            variable_map[name] = value
            prepared = re.sub(regex, f"<{name}>", prepared, count=1)
            query = re.sub(regex, value, query, count=1)
            match = regex.search(template, pos=start_index)
            count += 1
        # add endpoint
        manager.add_endpoint(command, prepared, BASIC_ENDPOINT_ENTRY)
        # get endpoint
        endpoint_value = manager.get_endpoint(command, query)
        # Assert
        assert endpoint_value is not None
        # returned values should have same count as template variables
        assert len(endpoint_value.values) == len(variable_map)
        for variable, expected_value in variable_map.items():
            assert variable in endpoint_value.values
            actual_value = endpoint_value.values.get(variable)
            assert actual_value == expected_value


def test_get_endpoint_doesnotexist_throws(manager):
    # Arrange
    command = "get"
    manager.add_command(command)
    endpoints = [
        "no_slashes_at_all",  # can begin/end with 0 or many slashes
        "/only_slash_at_start",
        "only_slash_at_end/",
        "/surrounding_slashes/",
        "////multiple_slashes/////////////////",
        "^[a-zA-Z0-9]+$"  # // endpoints can contain regex-life format, causing no issues
    ]
    # Act, Assert
    for endpoint in endpoints:
        with pytest.raises(EndpointManagerException) as e:
            try:
                manager.get_endpoint(command, endpoint)
            except Exception:
                raise
            else:
                print(f"Endpoint: {endpoint}")


def test_get_endpoint_commanddoesnotexist_throws(manager):
    # Arrange, Act, Assert
    with pytest.raises(EndpointManagerException) as e:
        manager.get_endpoint("get", "/")


def test_remove_endpoint(manager):
    # Arrange
    command = "get"
    endpoint = "/"
    manager.add_command(command)
    manager.add_endpoint(command, endpoint, BASIC_ENDPOINT_ENTRY)
    # Act, Assert
    removed = manager.remove_endpoint(command, endpoint)
    assert removed is not None
    assert removed.entry == BASIC_ENDPOINT_ENTRY
# endregion
