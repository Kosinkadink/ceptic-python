import select
import socket
import threading
import copy
import uuid

from functools import wraps
# multiprocessing-related imports
from sys import version_info
from multiprocessing import Process
from multiprocessing import Event as MP_Event
from multiprocessing import Queue as MP_Queue

if version_info < (3, 0):  # if running python 2
    from Queue import Empty
else:
    from queue import Empty

from ceptic.network import SocketCeptic
from ceptic.common import CepticRequest, CepticResponse, CepticStatusCode
from ceptic.common import command_settings
from ceptic.endpointmanager import EndpointManager
from ceptic.certificatemanager import CertificateManager, CertificateManagerException, create_ssl_config
from ceptic.streammanager import StreamManager, StreamException, StreamTotalDataSizeException
from ceptic.encode import EncodeGetter, UnknownEncodingException


def server_settings(port=9000, version="1.0.0",
                    headers_min_size=1024000, headers_max_size=1024000,
                    frame_min_size=1024000, frame_max_size=1024000,
                    body_max=102400000,
                    stream_min_timeout=5, stream_timeout=5,
                    send_buffer_size=102400000, read_buffer_size=102400000,
                    handler_max_count=0, block_on_start=False,
                    request_queue_size=10, max_parallel_count=1, verbose=False):
    settings = {"port": int(port),
                "version": str(version),
                "headers_min_size": int(headers_min_size),
                "headers_max_size": int(headers_max_size),
                "frame_min_size": int(frame_min_size),
                "frame_max_size": int(frame_max_size),
                "body_max": int(body_max),
                "stream_min_timeout": int(stream_min_timeout),
                "stream_timeout": int(stream_timeout),
                "send_buffer_size": int(send_buffer_size),
                "read_buffer_size": int(read_buffer_size),
                "handler_max_count": int(handler_max_count),
                "block_on_start": bool(block_on_start),
                "request_queue_size": int(request_queue_size),
                "max_parallel_count": int(max_parallel_count),
                "verbose": bool(verbose)}
    if settings["frame_min_size"] > settings["frame_max_size"]:
        settings["frame_min_size"] = settings["frame_max_size"]
    if settings["frame_min_size"] < 1000:
        raise ValueError("frame_min_size must be at least 1000; was {}".format(settings["frame_min_size"]))
    if settings["send_buffer_size"] < settings["frame_max_size"] + 38 or \
            settings["read_buffer_size"] < settings["frame_max_size"] + 38:
        raise ValueError("send and read buffer size must be greater than "
                         "frame_max_size+28 ({}); were {} and {}".format(settings["frame_max_size"] + 38,
                                                                         settings["send_buffer_size"],
                                                                         settings["read_buffer_size"]))
    if settings["max_parallel_count"] > 1:
        settings["use_processes"] = True
    else:
        settings["use_processes"] = False
    return settings


def begin_exchange(request):
    """
    Sends CepticResponse to client to start continuous exchange with server
    :param request: CepticRequest instance
    :return: StreamHandler instance from CepticRequest (request.stream)
    """
    response = CepticResponse(status=200)
    response.exchange = True
    request.stream.send_data(response.get_data())
    return request.stream


def basic_server_command(stream, request, endpoint_func, endpoint_dict):
    # get body if content length header is present
    if request.content_length:
        # TODO: Add file transfer functionality
        try:
            request.body = stream.get_full_data(max_length=request.content_length)
        except StreamTotalDataSizeException:
            stream.send_close("body received is greater than reported content_length")
            return
        except StreamException:
            return
    # set request stream to local stream
    request.stream = stream
    # perform command function with appropriate params
    try:
        response = endpoint_func(request, **endpoint_dict)
    except Exception as e:
        stream.send_close("ENDPOINT_FUNC caused Exception {},{}".format(type(e), str(e)))
        return
    # if CepticResponse not returned, try to parse as tuple and create CepticResponse
    if not isinstance(response, CepticResponse):
        try:
            if not isinstance(response, int):
                response_tuple = tuple(response)
            else:
                response_tuple = (response,)
            status = int(response_tuple[0])
            body = None
            headers = None
            errors = None
            # if error status, assume error message included
            if len(response_tuple) > 1:
                if CepticStatusCode.is_error(status):
                    errors = str(response_tuple[1])
                else:
                    body = str(response_tuple[1])
            # assume third item is headers
            if len(response_tuple) > 2:
                if not isinstance(response_tuple[2], dict):
                    raise ValueError("3rd argument must be type dict")
                headers = response_tuple[2]
            response = CepticResponse(status, body, headers, errors)
        except Exception as e:
            error_response = CepticResponse(500,
                                            errors="endpoint returned invalid data type '{}'' on server".format(
                                                type(response)))
            if request.config_settings["verbose"]:
                print("Exception type ({}) raised while generating response: {}".format(type(e), str(e)))
            stream.send_data(error_response.get_data())
            return
    stream.send_data(response.get_data())
    # if Content-Length header present, send response body
    if response.content_length:
        # TODO: Add file transfer functionality
        try:
            stream.send_data(response.body)
        except StreamException as e:
            stream.send_close("SERVER STREAM EXCEPTION: {},{}".format(type(e), str(e)))
            if request.config_settings["verbose"]:
                print("StreamException type ({}) raised while sending response body: {}".format(type(e), str(e)))
    # close connection
    stream.send_close("BASIC_SERVER_COMMAND COMPLETE")


def check_if_setting_bounded(client_min, client_max, server_min, server_max, name):
    error = None
    value = None
    if client_max <= server_max:
        if client_max < server_min:
            error = "client max {0} ({1}) is less than server's min {0} ({2})".format(
                name, client_max, server_min)
        else:
            value = client_max
    else:
        # since client max is greater than server max, check if server max is appropriate
        if client_min > server_max:
            # client min greater than server max, so not compatible
            error = "client min {0} ({1}) is greater than server's max {0} ({2})".format(
                name, client_min, server_max)
        # otherwise use server version
        else:
            value = server_max
    return error, value


class CepticServer(object):

    def __init__(self, settings, certfile=None, keyfile=None, cafile=None, secure=True):
        """
        General purpose Ceptic server
        :param settings: dict generated by server_settings
        :param certfile: server public key file (certificate)
        :param keyfile: server private key file
        :param cafile: optional client certificate for client verification
        :param secure: toggles if certificates/encryption should be used (default: True); recommended to be kept True
                       except for specific development purposes
        """
        self.settings = settings
        self.shouldStop = threading.Event()
        self.isDoneRunning = threading.Event()
        # set up endpoint manager
        self.endpointManager = EndpointManager.server()
        # set up certificate manager
        self.certificateManager = CertificateManager.server()
        self.setup_certificate_manager(certfile, keyfile, cafile, secure)
        # create StreamManager dict
        self.managerDict = {}
        self.manager_closed_event = threading.Event()
        self.clean_timeout = 0.5
        # runner list and socket queue for multiprocessing
        self.runnerList = []
        self.socket_queue = None
        # initialize
        self.initialize()

    def setup_certificate_manager(self, certfile=None, keyfile=None, cafile=None, secure=True):
        if certfile is None or keyfile is None:
            secure = False
        ssl_config = create_ssl_config(certfile=certfile, keyfile=keyfile, cafile=cafile, secure=secure)
        self.certificateManager.set_ssl_config(ssl_config)

    def initialize(self):
        """
        Initialize server configuration and processes
        :return: None
        """
        # set up config
        self.certificateManager.generate_context_tls()
        # add get command
        self.add_command("get")
        # add post command
        self.add_command("post")
        # add update command
        self.add_command("update")
        # add delete command
        self.add_command("delete")

    def add_command(self, command):
        """
        Add command name to endpoint manager; registers as a basic_client_command
        :param command: string command name
        :return: None
        """
        self.endpointManager.add_command(
            str(command),
            basic_server_command,
            command_settings(body_max=self.settings["body_max"])
        )

    def start(self):
        """
        Start running server
        :return: None
        """
        # run processes
        try:
            self.start_server()
        except Exception as e:
            self.stop()
            raise e

    def start_server(self):
        if self.settings["block_on_start"]:
            self.run_server()
        else:
            server_thread = threading.Thread(target=self.run_server)
            server_thread.daemon = True
            server_thread.start()

    def run_server(self, delay_time=0.1):
        """
        Start server loop, with the option to run a function repeatedly and set delay time in seconds
        :param delay_time: time to wait for a connection before repeating, default is 0.1 seconds
        :return: None
        """
        if self.settings["verbose"]:
            print('ceptic server started - version {} on port {}'.format(
                self.settings["version"], self.settings["port"]))
        # create a socket object
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        server_socket.settimeout(5)
        socket_list = []
        # get local machine name
        host = ""
        port = self.settings["port"]
        # bind to the port
        try:
            server_socket.bind((host, port))
        except Exception as e:
            if self.settings["verbose"]:
                print("Error while binding server_socket: {}".format(str(e)))
            self.shouldStop.set()
        # queue up to specified number of requests
        server_socket.listen(self.settings["request_queue_size"])
        socket_list.append(server_socket)
        clean_thread = None
        # if use_processes, start up corresponding amount of runners
        if self.settings["use_processes"]:
            self.start_runners(self.settings["max_parallel_count"])
        # else create a clean thread for managers
        else:
            clean_thread = threading.Thread(target=self.clean_managers)
            clean_thread.daemon = True
            clean_thread.start()

        while not self.shouldStop.is_set():
            ready_to_read, ready_to_write, in_error = select.select(socket_list, [], [], delay_time)
            for sock in ready_to_read:
                # establish a connection
                if sock == server_socket:
                    s, addr = server_socket.accept()
                    # enable socket blocking
                    s.setblocking(True)
                    # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    if self.settings["use_processes"]:
                        self.socket_queue.put([s, addr])
                    else:
                        new_thread = threading.Thread(
                            target=self.handle_new_socket,
                            args=(s, addr, self.settings, self.endpointManager, self.certificateManager,
                                  self.manager_closed_event, self.managerDict)
                        )
                        new_thread.daemon = True
                        new_thread.start()
        # shut down managers
        self.close_all_managers()
        # clean appropriate resources based on multiprocessing support
        if self.settings["use_processes"]:
            # close all runners
            self.close_all_runners()
        else:
            # wait for clean thread to finish
            clean_thread.join()
        # shut down server socket
        try:
            server_socket.shutdown(socket.SHUT_RDWR)
        except IOError as e:
            if self.settings["verbose"]:
                print("Error while shutting down server_socket: {}".format(str(e)))
        server_socket.close()
        self.isDoneRunning.set()

    @staticmethod
    def handle_new_socket(s, addr, settings, endpoint_manager, certificate_manager, manager_closed_event, manager_dict):
        """
        Handles a particular request, to be executed by another thread of process to not block main server loop
        :param s: basic socket instance
        :param addr: socket address
        :param settings:
        :param endpoint_manager:
        :param certificate_manager:
        :param manager_closed_event:
        :param manager_dict:
        :return: None
        """
        if settings["verbose"]:
            print("Got a connection from {}".format(addr))
        # wrap socket with TLS, handshaking happens automatically
        try:
            s = certificate_manager.wrap_socket(s)
        except CertificateManagerException as e:
            if settings["verbose"]:
                print("CertificateManagerException caught, connection terminated: {}".format(str(e)))
            s.close()
            return
        # wrap socket with SocketCeptic, to send length of message first
        s = SocketCeptic.wrap_socket(s)
        # get version
        client_version = s.recv_raw(16).strip()
        # get client frame_min_size
        client_frame_min_size_str = s.recv_raw(16).strip()
        # get client frame_max_size
        client_frame_max_size_str = s.recv_raw(16).strip()
        # get client headers_min_size
        client_headers_min_size_str = s.recv_raw(16).strip()
        # get client headers_max_size
        client_headers_max_size_str = s.recv_raw(16).strip()
        # get client stream_min_timeout
        client_stream_min_timeout_str = s.recv_raw(4).strip()
        # get client stream timeout
        client_stream_timeout_str = s.recv_raw(4).strip()
        # see if values are acceptable
        stream_settings = {"verbose": settings["verbose"],
                           "send_buffer_size": settings["send_buffer_size"],
                           "read_buffer_size": settings["read_buffer_size"]}
        errors = []
        # convert received values to int
        client_frame_min_size = None
        client_frame_max_size = None
        client_headers_min_size = None
        client_headers_max_size = None
        client_stream_min_timeout = None
        client_stream_timeout = None
        try:
            client_frame_min_size = int(client_frame_min_size_str)
            client_frame_max_size = int(client_frame_max_size_str)
            client_headers_min_size = int(client_headers_min_size_str)
            client_headers_max_size = int(client_headers_max_size_str)
            client_stream_min_timeout = int(client_stream_min_timeout_str)
            client_stream_timeout = int(client_stream_timeout_str)
        except ValueError:
            errors.append("received value must be an int, not string")
        if not errors:
            # check if server's frame size is acceptable
            error, value = check_if_setting_bounded(client_frame_min_size, client_frame_max_size,
                                                    settings["frame_min_size"], settings["frame_max_size"],
                                                    "frame size")
            if error:
                errors.append(error)
            else:
                stream_settings["frame_max_size"] = value
            # check if server's header size is acceptable
            error, value = check_if_setting_bounded(client_headers_min_size, client_headers_max_size,
                                                    settings["headers_min_size"],
                                                    settings["headers_max_size"],
                                                    "headers size")
            if error:
                errors.append(error)
            else:
                stream_settings["headers_max_size"] = value
            # check if server's timeout is acceptable
            error, value = check_if_setting_bounded(client_stream_min_timeout, client_stream_timeout,
                                                    settings["stream_min_timeout"],
                                                    settings["stream_timeout"],
                                                    "stream timeout")
            if error:
                errors.append(error)
            else:
                stream_settings["stream_timeout"] = value
        # send response
        # if errors present, send negative response with explanation
        if errors:
            s.send_raw("n")
            error_string = str(errors)[:1024]
            s.sendall(error_string)
            if settings["verbose"]:
                print("client not compatible with server settings, connection terminated")
            s.close()
            return
        # otherwise send positive response along with decided values
        else:
            stream_settings["handler_max_count"] = settings["handler_max_count"]
            s.send_raw("y")
            s.send_raw(format(stream_settings["frame_max_size"], ">16"))
            s.send_raw(format(stream_settings["headers_max_size"], ">16"))
            s.send_raw(format(stream_settings["stream_timeout"], ">4"))
            s.send_raw(format(stream_settings["handler_max_count"], ">4"))
        # create StreamManager
        manager_uuid = str(uuid.uuid4())
        manager = StreamManager.server(s, manager_uuid, stream_settings, CepticServer.handle_new_connection,
                                       (endpoint_manager,), manager_closed_event)
        manager_dict[manager_uuid] = manager
        manager.daemon = True
        manager.start()

    @staticmethod
    def handle_new_connection(stream, local_settings, endpoint_manager):
        # store errors in request
        errors = []
        # get request from request data
        request = None
        command_func = handler = variable_dict = None
        try:
            request = CepticRequest.from_data(stream.get_full_header_data())
        except UnknownEncodingException as e:
            errors.append(str(e))
        if not errors:
            # began checking validity of request
            # check that command and endpoint are of valid length
            if len(request.command) > 128:
                errors.append(
                    "command too long; should be no more than 128 characters, but was {}".format(len(request.command)))
            if len(request.endpoint) > 128:
                errors.append(
                    "endpoint too long; should be no more than 128 characters, but was {}".format(
                        len(request.endpoint)))
            # try to get endpoint objects from endpointManager
            try:
                command_func, handler, variable_dict, settings, settings_override = endpoint_manager.get_endpoint(
                    request.command, request.endpoint)
                # merge settings; endpoint settings take precedence over command settings
                settings_merged = copy.deepcopy(settings)
                if settings_override is not None:
                    settings_merged.update(settings_override)
                # set request settings to merged settings
                request.settings = settings_merged
                # set server settings as request's config settings
                request.config_settings = local_settings
            except KeyError:
                errors.append("endpoint of type {} not recognized: {}".format(request.command, request.endpoint))
            # check that headers are valid/proper
            errors.extend(CepticServer.check_new_connection_headers(request))
            # if no errors, send positive response and continue
        if not errors:
            stream.send_data(CepticResponse(200).get_data())
            # set stream compression, based on request header
            stream.set_encode(request.encoding)
            command_func(stream, request, handler, variable_dict)
        # otherwise send info back
        else:
            # send frame with error and bad status
            stream.send_data(CepticResponse(400, errors=errors).get_data())
            stream.send_close()

    @staticmethod
    def check_new_connection_headers(request):
        errors = []
        # check that content_length is of allowed length
        if request.content_length:
            # if content length is longer than set max body length, invalid
            if request.content_length > request.max_content_length:
                errors.append("Content-Length ({}) exceeds server's allowed max body length of {}".format(
                    request.content_length,
                    request.max_content_length))
        # check that encoding is recognized and valid
        if request.encoding:
            valid, error = EncodeGetter.check(request.encoding)
            if not valid:
                errors.append("Encoding is not valid; {}".format(error))
        return errors

    def route(self, endpoint, command, settings=None):
        """
        Decorator for adding endpoints to server instance
        :param endpoint: string url for route to be added as an endpoint
        :param command: string Ceptic command name (get, post, update, delete)
        :param settings: optional dict generate by command_settings
        """
        def decorator_route(func):
            self.endpointManager.add_endpoint(command, endpoint, func, settings)
            return func

        return decorator_route

    def stop(self, blocking=True):
        """
        Properly begin to stop server; tells server loop to stop
        If blocking is True, waits until server is done closing
        :param blocking: boolean for if should block until server fully closes
        :return: None
        """
        self.shouldStop.set()
        if blocking and not self.is_stopped():
            self.wait_until_not_running()

    def wait_until_not_running(self):
        """
        Blocks until server fully closes
        :return: None
        """
        self.isDoneRunning.wait()

    def is_stopped(self):
        """
        Returns True if server is not running
        """
        return self.shouldStop.is_set() and self.isDoneRunning.is_set()

    def is_running(self):
        """
        Returns True if server is running
        """
        return not self.shouldStop.is_set() and not self.isDoneRunning.is_set()

    def close_all_managers(self):
        """
        Stops and removes all managers
        :return: None
        """
        keys = list(self.managerDict)
        for key in keys:
            try:
                self.managerDict[key].stop()
            except KeyError:
                pass
        for key in keys:
            try:
                self.managerDict[key].wait_until_not_running()
            except KeyError:
                pass
            self.remove_manager(key)

    def clean_managers(self):
        """
        Loop for cleaning closed or timed out managers until server is signalled to stop
        :return: None
        """
        while not self.shouldStop.is_set():
            manager_closed = self.manager_closed_event.wait(self.clean_timeout)
            if manager_closed:
                self.manager_closed_event.clear()
                managers = list(self.managerDict)
                for manager_name in managers:
                    manager = self.managerDict.get(manager_name)
                    if manager and manager.is_stopped():
                        self.remove_manager(manager_name)

    def remove_manager(self, manager_uuid):
        """
        Removes manager with corresponding UUID from managerDict
        :param manager_uuid: string form of UUID
        :return: None
        """
        try:
            self.managerDict.pop(manager_uuid)
        except KeyError:
            pass

    def start_runners(self, count):
        self.socket_queue = MP_Queue()
        for n in range(count):
            name = "Runner{}".format(n)
            new_runner = HandleNewSocketRunner(self.socket_queue, self.settings, self.endpointManager,
                                               self.certificateManager, self.clean_timeout, name)
            new_runner.daemon = True
            new_runner.start()
            # add runner to runnerList
            self.runnerList.append(new_runner)

    def close_all_runners(self):
        # stop all runners
        for runner in self.runnerList:
            runner.stop()
        # wait for runners to finish running
        for runner in self.runnerList:
            runner.join()
        # remove all runners
        del self.runnerList[:]


class HandleNewSocketRunner(Process):
    """
    Handles sockets and corresponding managers in a separate process
    """

    def __init__(self, socket_queue, settings, endpoint_manager, certificate_manager, timeout=0.5, name="DefaultName"):
        Process.__init__(self)
        self.socket_queue = socket_queue
        self.settings = settings
        self.endpoint_manager = endpoint_manager
        self.certificate_manager = certificate_manager
        self.timeout = timeout
        self.name = name
        # close event
        self.shouldStop = MP_Event()
        # manager storage
        self.managerDict = {}
        self.manager_closed_event = MP_Event()

    def run(self):
        # start clean thread
        clean_thread = threading.Thread(target=self.clean_managers)
        clean_thread.daemon = True
        clean_thread.start()
        # keep receiving and handling sockets while not stopped
        while not self.shouldStop.is_set():
            try:
                handle_args = self.socket_queue.get(block=True, timeout=self.timeout)
                # add arguments necessary for handle_new_socket
                handle_args.extend([self.settings, self.endpoint_manager, self.certificate_manager,
                                   self.manager_closed_event, self.managerDict])
                new_handle_call = threading.Thread(target=CepticServer.handle_new_socket, args=handle_args)
                new_handle_call.daemon = True
                new_handle_call.start()
            except Empty:
                pass
        # close all managers
        self.close_all_managers()
        # wait for clean thread to stop
        clean_thread.join()

    def clean_managers(self):
        """
        Loop for cleaning closed or timed out managers until server is signalled to stop
        :return: None
        """
        while not self.shouldStop.is_set():
            manager_closed = self.manager_closed_event.wait(self.timeout)
            if manager_closed:
                self.manager_closed_event.clear()
                managers = list(self.managerDict)
                for manager_name in managers:
                    manager = self.managerDict.get(manager_name)
                    if manager and manager.is_stopped():
                        self.remove_manager(manager_name)

    def close_all_managers(self):
        """
        Stops and removes all managers
        :return: None
        """
        keys = list(self.managerDict)
        for key in keys:
            try:
                self.managerDict[key].stop()
            except KeyError:
                pass
        for key in keys:
            try:
                self.managerDict[key].wait_until_not_running()
            except KeyError:
                pass
            self.remove_manager(key)

    def remove_manager(self, manager_uuid):
        """
        Removes manager with corresponding UUID from managerDict
        :param manager_uuid: string form of UUID
        :return: None
        """
        try:
            self.managerDict.pop(manager_uuid)
        except KeyError:
            pass

    def stop(self):
        self.shouldStop.set()
