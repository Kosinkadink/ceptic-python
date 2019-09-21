import pytest
from sys import version_info
if version_info < (3,0): # if running python 2
    from testingfixtures import add_surrounding_dir_to_path
    # add surrounding dir to path to enable importing
    add_surrounding_dir_to_path()

from ceptic.managers.endpointmanager import EndpointManager,EndpointClientManager,EndpointServerManager
from ceptic.managers.endpointmanager import EndpointManagerException
from ceptic.common import create_command_settings

# HELPERS:
def helper_add_test_command_to_EndpointServerManager(manager,command_name):
    def command_func():
        pass
    manager.add_command(command="get",
                        command_func=command_name,
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
                        )
# END HELPERS


# TESTS:
# Client Tests
def test_client_create_manager():
    manager = EndpointManager.client()
    assert isinstance(manager,EndpointClientManager)

def test_client_add_command():
    manager = EndpointManager.client()
    def command_func():
        pass
    manager.add_command(command="get",
                        func=command_func,
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
                        )

def test_client_get_command():
    manager = EndpointManager.client()
    def command_func():
        pass
    manager.add_command(command="get",
                        func=command_func,
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
                        )
    func,settings = manager.get_command("get")
    assert func is command_func
    assert settings["maxMsgLength"] == 1024
    assert settings["maxBodyLength"] == 2048

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
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
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
    assert isinstance(manager,EndpointServerManager)

def test_server_add_command():
    manager = EndpointManager.server()
    def command_func():
        pass
    manager.add_command(command="get",
                        command_func=command_func,
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
                        )

def test_server_get_command():
    manager = EndpointManager.server()
    def command_func():
        pass
    manager.add_command(command="get",
                        command_func=command_func,
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
                        )
    endpointMap,func,settings = manager.get_command("get")
    assert isinstance(endpointMap,dict)
    assert len(endpointMap) == 0
    assert func is command_func
    assert settings["maxMsgLength"] == 1024
    assert settings["maxBodyLength"] == 2048

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
                        settings=create_command_settings(
                            maxMsgLength=1024,
                            maxBodyLength=2048)
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
    helper_add_test_command_to_EndpointServerManager(manager,"get")
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
    endpointMap,func,settings = manager.commandMap["get"]


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
    helper_add_test_command_to_EndpointServerManager(manager,"get")
    def endpoint_handler():
        pass
    good_endpoints = []
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
    # there can be multiple braces between slashes as long as they are not consecutive
    good_endpoints.append("<good>.<braces>")
    good_endpoints.append("<good>good<braces>")
    # all good endpoints should NOT raise exception
    for good_endpoint in good_endpoints:
        try:
            manager.add_endpoint(command="get",
                                 endpoint=good_endpoint,
                                 handler=endpoint_handler,
                                 settings_override=None)
        except EndpointManagerException as e:
            pytest.fail("Raised exception '{}' for endpoint: {}".format(str(e),good_endpoint))



def test_server_add_endpoint_bad_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager,"get")
    def endpoint_handler():
        pass
    bad_endpoints = []
    # endpoint cannot be blank
    bad_endpoints.append("")
    # non-alpha numeric or non -.<>_/ symbols are not allowed
    bad_chars = "!@#$%^&*()=+`~[}{]\\|;:\"',"
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
    # all bad endpoints should raise exception
    for bad_endpoint in bad_endpoints:
        try:
            manager.add_endpoint(command="get",
                                 endpoint=bad_endpoint,
                                 handler=endpoint_handler,
                                 settings_override=None)
        except EndpointManagerException:
            pass
        else:
            pytest.fail("Did NOT raise EndpointManagerException for endpoint: {}".format(bad_endpoint))    

# TODO: finish get_endpoint and remove_endpoint tests
def test_server_get_endpoint():
    manager = EndpointManager.server()
    helper_add_test_command_to_EndpointServerManager(manager,"get")
    def endpoint_handler():
        pass
    manager.add_endpoint(command="get",
                             endpoint="/",
                             handler=endpoint_handler,
                             settings_override=None)

# END TESTS


# TEST SETUP
def setup_function(function):
    pass

def teardown_function(function):
    pass

def setup_module(module):
    pass

def teardown_module(module):
    pass
# END TEST SETUP
