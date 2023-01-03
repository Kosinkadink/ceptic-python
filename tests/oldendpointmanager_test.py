import pytest
from oldceptic.endpointmanager import EndpointManager, EndpointClientManager, EndpointServerManager
from oldceptic.endpointmanager import EndpointManagerException
from oldceptic.common import command_settings


# HELPERS:
def helper_add_test_command_to_EndpointServerManager(manager, command_name):
    manager.add_command(command="get",
                        command_func=command_name,
                        settings=command_settings(body_max=1024)
                        )
# END HELPERS


# TESTS:

# Client Tests
def test_client_create_manager():
    manager = EndpointManager.client()
    assert isinstance(manager, EndpointClientManager)


def test_client_add_command():
    manager = EndpointManager.client()

    def command_func():
        pass

    manager.add_command(command="get",
                        func=command_func,
                        settings=command_settings(body_max=1024)
                        )


def test_client_get_command():
    manager = EndpointManager.client()

    def command_func():
        pass

    manager.add_command(command="get",
                        func=command_func,
                        settings=command_settings(body_max=1024)
                        )
    func, settings = manager.get_command("get")
    assert func is command_func
    assert settings["body_max"] == 1024


def test_client_get_command_does_not_exist():
    manager = EndpointManager.client()
    # expect KeyError when command doesn't exist
    with pytest.raises(KeyError):
        manager.get_command("get")


def test_client_remove_command():
    manager = EndpointManager.client()

    def command_func():
        pass

    manager.add_command(command="get",
                        func=command_func,
                        settings=command_settings(body_max=1024)
                        )
    # make sure get command works
    try:
        manager.get_command("get")
    except Exception as e:
        pytest.fail("Unexpected exception: {}".format(str(e)))
    # delete command
    assert manager.remove_command("get") is None
    # expect KeyError due to command no longer existing
    with pytest.raises(KeyError):
        manager.get_command("get")
    # removing non-existing command should return nothing
    assert manager.remove_command("get") is None


# Server Tests
def test_server_create_manager():
    manager = EndpointManager.server()
    assert isinstance(manager, EndpointServerManager)


def test_server_add_command():
    manager = EndpointManager.server()

    def command_func():
        pass

    manager.add_command(command="get",
                        command_func=command_func,
                        settings=command_settings(body_max=1024)
                        )


def test_server_get_command():
    manager = EndpointManager.server()

    def command_func():
        pass

    manager.add_command(command="get",
                        command_func=command_func,
                        settings=command_settings(body_max=1024)
                        )
    endpointMap, func, settings = manager.get_command("get")
    assert isinstance(endpointMap, dict)
    assert len(endpointMap) == 0
    assert func is command_func
    assert settings["body_max"] == 1024


def test_server_get_command_does_not_exist():
    manager = EndpointManager.server()
    # expect KeyError when command doesn't exist
    with pytest.raises(KeyError):
        manager.get_command("get")


def test_server_remove_command():
    manager = EndpointManager.server()

    def command_func():
        pass

    manager.add_command(command="get",
                        command_func=command_func,
                        settings=command_settings(body_max=1024)
                        )
    # make sure get command works
    try:
        manager.get_command("get")
    except Exception as e:
        pytest.fail("Unexpected exception: {}".format(str(e)))
    # delete command
    assert manager.remove_command("get") is None
    # expect KeyError due to command no longer existing
    with pytest.raises(KeyError):
        manager.get_command("get")
    # removing non-existing command should return nothing
    assert manager.remove_command("get") is None


def test_server_add_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    try:
        manager.add_endpoint(command="get",
                             endpoint="/",
                             handler=endpoint_handler,
                             settings_override=None)
    except EndpointManagerException as e:
        pytest.fail("Unexpected EndpointManagerException: {}".format(e))
    # endpoint info should be stored properly
    endpointMap, func, settings = manager.commandMap["get"]
    assert isinstance(endpointMap, dict)
    assert func is not None
    assert settings is not None


def test_server_add_endpoint_command_does_not_exist():
    manager = EndpointManager.server()

    def endpoint_handler():
        pass

    with pytest.raises(EndpointManagerException):
        manager.add_endpoint(command="get",
                             endpoint="/",
                             handler=endpoint_handler,
                             settings_override=None)


def test_server_add_endpoint_good_endpoints():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    good_endpoints = list()
    # endpoint can be a single slash
    good_endpoints.append("/")
    # endpoint can be composed of any alpha-numerics as well as -.<>_/ characters
    good_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-._"
    for char in good_chars:
        good_endpoints.append("test/{}".format(char))
        good_endpoints.append("{}/test".format(char))
        good_endpoints.append(char)
    # endpoint can contain braces for variable portions or URL; have to match
    good_endpoints.append("good/<braces>")
    good_endpoints.append("<braces>")
    good_endpoints.append("<good>/braces")
    # variable name can start with underscore
    good_endpoints.append("<_underscore>/in/variable/name")
    # endpoint can start or end with multiple (or no) slashes
    good_endpoints.append("no_slashes_at_all")
    good_endpoints.append("/only_slash_at_start")
    good_endpoints.append("only_slash_at_end/")
    good_endpoints.append("/surrounding_slashes/")
    good_endpoints.append("////multiple_slashes/////////////////")
    # all good endpoints should NOT raise exception
    for endpoint in good_endpoints:
        try:
            manager.add_endpoint(command="get",
                                 endpoint=endpoint,
                                 handler=endpoint_handler,
                                 settings_override=None)
        except EndpointManagerException as e:
            pytest.fail("Raised EndpointManagerException '{}' for endpoint: {}".format(str(e), endpoint))


def test_server_add_endpoint_bad_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    # add a valid endpoint
    manager.add_endpoint(command="get",
                         endpoint="willalreadyexist",
                         handler=endpoint_handler)
    # store bad endpoints to try out
    bad_endpoints = list()
    # endpoint cannot be blank
    bad_endpoints.append("")
    # non-alpha numeric or non -.<>_/ symbols are not allowed
    bad_chars = "!@#$%^&*()=+`~[}{]\\|;:\"', "
    for char in bad_chars:
        bad_endpoints.append("test/{}".format(char))
    # consecutive slashes in the middle are not allowed
    bad_endpoints.append("bad//endpoint")
    bad_endpoints.append("/bad/endpoint//2/")
    # braces cannot be across a slash
    bad_endpoints.append("bad/<bra/ces>")
    # braces cannot have nothing in between
    bad_endpoints.append("bad/<>/braces")
    # braces must close
    bad_endpoints.append("unmatched/<braces")
    bad_endpoints.append("unmatched/<braces>>")
    bad_endpoints.append("unmatched/<braces>/other>")
    bad_endpoints.append(">braces")
    # braces cannot contain other braces
    bad_endpoints.append("unmatched/<<braces>>")
    bad_endpoints.append("unmatched/<b<race>s>")
    # braces cannot be placed directly adjacent to each other
    bad_endpoints.append("multiple/<unslashed><braces>")
    # braces cannot be placed more than once between slashes
    bad_endpoints.append("multiple/<braces>.<between>")
    bad_endpoints.append("multiple/<braces>.<between>/slashes")
    bad_endpoints.append("<bad>bad<braces>")
    # variable name in braces cannot start with a number
    bad_endpoints.append("starts/<1withnumber>")
    # endpoint cannot already exist; slash at beginning or end makes no difference
    bad_endpoints.append("willalreadyexist")
    bad_endpoints.append("/willalreadyexist")
    bad_endpoints.append("willalreadyexist/")
    bad_endpoints.append("///willalreadyexist/////")
    # all bad endpoints should raise exception
    for endpoint in bad_endpoints:
        try:
            manager.add_endpoint(command="get",
                                 endpoint=endpoint,
                                 handler=endpoint_handler)
        except EndpointManagerException:
            pass
        else:
            pytest.fail("Did NOT raise EndpointManagerException for endpoint: {}".format(endpoint))


def test_server_get_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    manager.add_endpoint(command="get",
                         endpoint="/",
                         handler=endpoint_handler,
                         settings_override=None)
    command_func, handler, variable_dict, settings, settings_override = manager.get_endpoint("get", "/")
    assert handler is endpoint_handler
    assert len(variable_dict) == 0
    assert settings is not None
    assert settings_override is None


def test_server_get_endpoint_with_variables():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    #
    var_endpoint_tests = ["test/<>",
                          "<>/<>",
                          "tests/<>/<>",
                          "tests/<>/other/<>",
                          "<>/tests/variable0/<>",
                          "<>/<>/<>/<>/<>",
                          "<>/<>/<>/<>/<>/test"
                          ]

    for var_endpoint in var_endpoint_tests:
        # get variable count and names, in order
        var_endpoint_query = var_endpoint
        var_count = 0
        var_names = []
        var_values = []
        while var_endpoint.find("<>") != -1:
            var_names.append("variable{}".format(var_count))
            var_values.append("varvalue{}".format(var_count))
            var_endpoint = var_endpoint.replace("<>", "<{}>".format(var_names[-1]), 1)
            var_endpoint_query = var_endpoint_query.replace("<>", var_values[-1], 1)
            var_count += 1
        # add endpoint
        manager.add_endpoint(command="get",
                             endpoint=var_endpoint,
                             handler=endpoint_handler)
        command_func, handler, variable_dict, settings, settings_override = manager.get_endpoint("get",
                                                                                                 var_endpoint_query)
        assert len(variable_dict) == len(var_values)
        current_var_index = 0
        while current_var_index < var_count:
            name = var_names[current_var_index]
            value = var_values[current_var_index]
            if variable_dict.get(name) is None:
                pytest.fail("variable_dict did not have expected variable '{}' "
                            "for endpoint: {}".format(name, var_endpoint_query))
            if variable_dict.get(name) != value:
                pytest.fail(
                    "variable_dict did not have expected value '{}' for name '{}' for endpoint: {}. Instead, "
                    "variable_dict was: {}".format(
                        value, name, var_endpoint_query, str(variable_dict)))
            current_var_index += 1


def test_server_get_endpoint_valid_endpoint_but_does_not_exist():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")
    # valid endpoints to try out
    valid_endpoints = []
    # endpoint query can contain any printable ASCII symbol aside from \ and space
    good_chars = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    # single characters should work
    for char in good_chars:
        valid_endpoints.append(char)
        valid_endpoints.append("validendpoint{}".format(char))
    # can begin/end with 0 or many slashes
    valid_endpoints.append("no_slashes_at_all")
    valid_endpoints.append("/only_slash_at_start")
    valid_endpoints.append("only_slash_at_end/")
    valid_endpoints.append("/surrounding_slashes/")
    valid_endpoints.append("////multiple_slashes/////////////////")
    # endpoints can contain regex-like format that will be escaped, causing no issues
    valid_endpoints.append("^[a-zA-Z0-9]+$")
    # all valid endpoints should raise a KeyError, as they are valid but are not registered
    for endpoint in valid_endpoints:
        try:
            manager.get_endpoint("get", endpoint)
        except KeyError:
            pass
        except Exception as e:
            pytest.fail("Raised unexpected {} with message '{}' for endpoint: {}".format(type(e), str(e), endpoint))
        else:
            pytest.fail("Did NOT raise KeyError for endpoint: {}".format(endpoint))


def test_server_get_endpoint_invalid_query():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")
    # invalid endpoints to try out
    invalid_endpoints = []
    # endpoint query cannot contain spaces or back slashes
    bad_chars = " \\"
    for char in bad_chars:
        invalid_endpoints.append(char)
        invalid_endpoints.append("invalid{}chars".format(char))
    # endpoint query cannot have consecutive slashes in the middle
    invalid_endpoints.append("invalid//slashes")
    invalid_endpoints.append("/invalid////slashes")
    invalid_endpoints.append("invalid//slashes/")
    invalid_endpoints.append("/invalid//slashes/")
    # endpoint query cannot be empty
    invalid_endpoints.append("")

    # invalid endpoints should raise an EndpointManagerException, NOT KeyError or nothing
    for endpoint in invalid_endpoints:
        try:
            manager.get_endpoint("get", endpoint)
        except EndpointManagerException:
            pass
        except Exception as e:
            pytest.fail(
                "Raised unexpected {} exception with message '{}' for endpoint: {}".format(type(e), str(e), endpoint))
        else:
            pytest.fail("Did NOT raise EndpointManagerException for endpoint: {}".format(endpoint))


def test_server_get_endpoint_command_does_not_exist():
    manager = EndpointManager.server()
    with pytest.raises(EndpointManagerException):
        manager.get_endpoint("get", "/")


def test_server_remove_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager, "get")

    def endpoint_handler():
        pass

    manager.add_endpoint(command="get",
                         endpoint="/",
                         handler=endpoint_handler,
                         settings_override=None)
    # make sure get endpoint works
    try:
        manager.get_endpoint("get", "/")
    except Exception as e:
        pytest.fail("Unexpected {} exception: {}".format(type(e), str(e)))
    # delete command
    assert manager.remove_endpoint("get", "/") is None
    # expect KeyError due to command no longer existing
    try:
        manager.get_endpoint("get", "/")
    except KeyError:
        pass
    except Exception as e:
        pytest.fail("Unexpected {} exception: {}".format(type(e), str(e)))
    else:
        pytest.fail("Did NOT throw KeyError; get_endpoint call here should fail")
    # removing non-existing command should return nothing
    assert manager.remove_endpoint("get", "/") is None

# END TESTS
