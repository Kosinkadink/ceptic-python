import traceback
import uuid

import select
import ssl
import socket
from threading import Thread
from typing import Union
from uuid import UUID

from ceptic.common import Constants, CepticException, CepticStatusCode
from ceptic.encode import EncodeGetter, UnknownEncodingException
from ceptic.endpoint import EndpointManager, CommandSettings, EndpointEntry, EndpointValue, EndpointManagerException, \
    ServerSettings
from ceptic.interfaces import IRemovableManagers
from ceptic.net import SocketCeptic
from ceptic.security import SecuritySettings
from ceptic.stream import StreamFrame, StreamHandlerInternal, StreamManager, CepticRequest, StreamSettings, \
    CepticResponse, StreamTotalDataSizeException, StreamException, StreamHandler


class SettingsBoundedResult(object):
    def __init__(self, error: str, value: int) -> None:
        self.error = error
        self.value = value

    def has_error(self) -> bool:
        return self.error is not None and len(self.error) > 0


def check_if_settings_bounded(client_min: int, client_max: int, server_min: int, server_max: int,
                              setting_name: str) -> SettingsBoundedResult:
    error = ""
    value = -1
    if client_max <= server_max:
        if client_max < server_min:
            error = f"client max {setting_name} ({client_max}) is less than server's min ({server_min})"
        else:
            value = client_max
    # since client is greater than server max, check if server max is appropriate
    if client_min > server_max:
        # client min greater than server max, so not compatible
        error = f"client min {setting_name} ({client_min}) is greater than server's max ({server_max})"
    # otherwise use server max
    else:
        value = server_max
    return SettingsBoundedResult(error=error, value=value)


class CepticServer(IRemovableManagers):
    def __init__(self, security: SecuritySettings, settings: ServerSettings = None):
        super()
        self.managers: dict[UUID, StreamManager] = dict()
        self.settings = settings if settings else ServerSettings()
        self.security = security
        self.ssl_context: Union[ssl.SSLContext, None] = None
        self.endpoint_manager = EndpointManager(self.settings)
        self.setup_security()
        self.run_thread = Thread(target=self.run)
        self.run_thread.daemon = self.settings.daemon
        self.should_stop = False
        self.stopped = False
        self.delay = 0.5

    # region Security
    def setup_security(self) -> None:
        """
        Sets up security for CepticServer, or throws SecurityException if something is misconfigured in provided
        SecuritySettings.
        Returns
        -------
        None
        """
        if not self.security.secure:
            return None
        # if ssl_context exists on security settings, use it
        if self.security.ssl_context:
            self.ssl_context = self.security.ssl_context
            return
        # otherwise, create default secure settings and customize them if needed
        ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        # if local_cert present, attempt to load server cert and key
        if self.security.local_cert:
            ssl_context.load_cert_chain(certfile=self.security.local_cert, keyfile=self.security.local_key,
                                        password=self.security.key_password)
        # if remote_cert present, attempt to load client cert
        if self.security.remote_cert or self.security.remote_certs_path:
            ssl_context.load_verify_locations(cafile=self.security.remote_cert,
                                              capath=self.security.remote_certs_path)
        ssl_context.check_hostname = self.security.verify_remote
        self.ssl_context = ssl_context

    @property
    def secure(self) -> bool:
        return self.security.secure

    # endregion

    # region Add Commands and Routes
    def add_command(self, command: str, settings: CommandSettings = None) -> None:
        self.endpoint_manager.add_command(command, settings)

    def add_route(self, command: str, endpoint: str, entry: EndpointEntry, settings: CommandSettings = None) -> None:
        self.endpoint_manager.add_endpoint(command, endpoint, entry, settings)

    # endregion

    # region Start
    def start(self) -> None:
        self.run_thread.start()

    def run(self) -> None:
        server_socket: Union[socket.socket, None] = None
        try:
            if self.settings.verbose:
                print(f"ceptic server started - version {self.settings.version} on port {self.settings.port} "
                      f"(secure: {self.security.secure})")
            # create tcp socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            server_socket.settimeout(5)
            # bind to port
            try:
                server_socket.bind(("", self.settings.port))
            except Exception as e:
                if self.settings.verbose:
                    print(f"Issue while binding server_socket: {str(e)}")
                self.should_stop = True
                return
            # queue up to request queue size
            server_socket.listen(self.settings.request_queue_size)
            socket_list = [server_socket]
            # repeatedly accept client sockets
            while not self.should_stop:
                ready_to_read, ready_to_write, in_error = select.select(socket_list, [], [], self.delay)
                for sock in ready_to_read:
                    # server socket is only one in list, so assume it's the one
                    # establish a connection
                    raw_s, addr = server_socket.accept()
                    # enable socket blocking and no delay
                    raw_s.setblocking(True)
                    raw_s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    client_thread = Thread(target=self.create_new_manager, args=(raw_s, addr))
                    client_thread.daemon = True
                    client_thread.start()
        except Exception as e:
            raise
        finally:
            # server is closing
            self.should_stop = True
            # shut down server socket
            if server_socket:
                try:
                    server_socket.shutdown(socket.SHUT_RDWR)
                except IOError as e:
                    if self.settings.verbose:
                        print(f"Issue while shutting down server_socket: {type(e)},{str(e)}")
                try:
                    server_socket.close()
                except Exception as e:
                    if self.settings.verbose:
                        print(f"Issue while closing server_socket: {type(e)},{str(e)}")
            # shut down managers
            self.remove_all_managers()
            self.stopped = True

    # endregion

    # region Stop
    def stop(self):
        self.should_stop = True

    def is_stopped(self):
        return self.stopped
    # endregion

    # region Connection
    def handle_new_connection(self, stream: StreamHandlerInternal) -> None:
        # store errors in request
        errors = []
        # get request from request data
        request = CepticRequest.from_data(stream.read_header_data().data)
        # begin checking validity of request
        # check that command and endpoint are of valid length
        if len(request.command) > Constants.COMMAND_LENGTH:
            errors.append(f"command too long; should be no more than {Constants.COMMAND_LENGTH} but was "
                          f"{len(request.command)}")
        if len(request.endpoint) > Constants.ENDPOINT_LENGTH:
            errors.append(f"endpoint too long; should be no more than {Constants.ENDPOINT_LENGTH} but was "
                          f"{len(request.endpoint)}")
        # if no errors yet, get endpoint from endpoint manager
        endpoint_value: Union[EndpointValue, None] = None
        if not errors:
            try:
                # get endpoint value from endpoint manager
                endpoint_value = self.endpoint_manager.get_endpoint(request.command, request.endpoint)
                # check that headers are valid
                errors.extend(self.check_new_connection_headers(request))
            except EndpointManagerException as e:
                errors.append(str(e))
        # if errors or no endpoint value found, send CepticResponse with BadRequest
        if errors or endpoint_value is None:
            stream.send_response(CepticResponse(CepticStatusCode.BAD_REQUEST, errors=errors))
            stream.send_close()
            return
        # otherwise send positive response and continue with endpoint function
        stream.send_response(CepticResponse(CepticStatusCode.OK))
        # set stream encoding, based on request header
        try:
            stream.set_encode(request.encoding)
        except UnknownEncodingException as e:
            stream.send_close(str(e))
            return
        # get body if content length header is present
        if request.content_length:
            try:
                request.body = stream.read_raw(request.content_length)
            except StreamTotalDataSizeException:
                stream.send_close("body received is greater than reported Content-Length")
                return
        # set request stream
        request.stream = StreamHandler(stream)
        # perform endpoint function and get back response
        response = endpoint_value.execute(request)
        # send response
        stream.send_response(response)
        # send body if content length header present
        if response.content_length:
            try:
                stream.send_data(response.body)
            except StreamException as e:
                stream.send_close("Server stream exception occurred")
                if self.settings.verbose:
                    print(f"StreamException type {type(e)} raised while sending response body: {str(e)}")
                return
        # close connection
        stream.send_close("Server command complete")
    # endregion

    # region Managers
    def create_new_manager(self, raw_s: socket.socket, addr: any) -> None:
        try:
            if self.settings.verbose:
                print(f"Got a connection from {addr}")
            # wrap with SSL
            s: Union[SocketCeptic, None] = None
            if self.security.secure:
                try:
                    ssl_s: ssl.SSLSocket = self.ssl_context.wrap_socket(raw_s, server_side=True)
                    # wrap as SocketCeptic
                    s = SocketCeptic(ssl_s)
                except ssl.SSLError as e:
                    raise CepticException(f"Could not authenticate client: {e}") from e
            else:
                # wrap as SocketCeptic
                s = SocketCeptic(raw_s)

            # get client version
            client_version = s.recv_raw_str(16).strip()
            # get client frame min size
            client_frame_min_size_str = s.recv_raw_str(16).strip()
            # get client frame max size
            client_frame_max_size_str = s.recv_raw_str(16).strip()
            # get client headers min size
            client_headers_min_size_str = s.recv_raw_str(16).strip()
            # get client headers max size
            client_headers_max_size_str = s.recv_raw_str(16).strip()
            # get client stream min timeout
            client_stream_min_timeout_str = s.recv_raw_str(4).strip()
            # get client stream timeout
            client_stream_timeout_str = s.recv_raw_str(4).strip()

            errors = []
            stream_settings: Union[StreamSettings, None] = None
            # see if values are acceptable
            try:
                client_frame_min_size = int(client_frame_min_size_str)
                client_frame_max_size = int(client_frame_max_size_str)
                client_headers_min_size = int(client_headers_min_size_str)
                client_headers_max_size = int(client_headers_max_size_str)
                client_stream_min_timeout = int(client_stream_min_timeout_str)
                client_stream_timeout = int(client_stream_timeout_str)
                # check value bounds
                frame_max_size = check_if_settings_bounded(client_frame_min_size, client_frame_max_size,
                                                           self.settings.frame_min_size, self.settings.frame_max_size,
                                                           "frame size")
                headers_max_size = check_if_settings_bounded(client_headers_min_size, client_headers_max_size,
                                                             self.settings.headers_min_size,
                                                             self.settings.headers_max_size,
                                                             "header size")
                stream_timeout = check_if_settings_bounded(client_stream_min_timeout, client_stream_timeout,
                                                           self.settings.stream_min_timeout,
                                                           self.settings.stream_timeout,
                                                           "frame size")
                # add errors, if applicable
                if frame_max_size.has_error():
                    errors.append(frame_max_size.error)
                if headers_max_size.has_error():
                    errors.append(headers_max_size.error)
                if stream_timeout.has_error():
                    errors.append(stream_timeout.error)
                # create stream settings
                stream_settings = StreamSettings(self.settings.send_buffer_size, self.settings.read_buffer_size,
                                                 frame_max_size.value, headers_max_size.value, stream_timeout.value,
                                                 self.settings.handler_max_count)
                stream_settings.verbose = self.settings.verbose
            except ValueError:
                errors.append(f"Client's thresholds were not all integers:"
                              f"{client_frame_min_size_str},{client_frame_max_size_str},"
                              f"{client_headers_min_size_str},{client_headers_max_size_str},"
                              f"{client_stream_min_timeout_str},{client_stream_timeout_str}")
            # send response
            # if errors present, send negative response with explanation
            if len(errors) > 0 or not stream_settings:
                s.send_raw_str("n")
                error_string = ", ".join(errors)[0:1024]  # limit error str to max 1024 characters
                s.send_str(error_string)
                if self.settings.verbose:
                    print("Client not compatible with server settings, connection terminated.")
                s.close()
                return
            # otherwise send positive response along with decided values
            s.send_raw_str("y")
            s.send_raw_str(f"{stream_settings.frame_max_size:>16}")
            s.send_raw_str(f"{stream_settings.headers_max_size:>16}")
            s.send_raw_str(f"{stream_settings.stream_timeout:>4}")
            s.send_raw_str(f"{stream_settings.handler_max_count:>4}")
            # create manager
            manager = StreamManager(s, uuid.uuid4(), "manager", stream_settings, removable=self, is_server=True)
            self.add_manager(manager)
            manager.start()
        except CepticException as e:
            if self.settings.verbose:
                print(f"Issue with create_new_manager: {type(e)},{str(e)}")
        except Exception as e:
            if self.settings.verbose:
                print(f"Unexpected issue with create_new_manager {type(e)},{str(e)}")
                raise

    def add_manager(self, manager: StreamManager) -> None:
        # add manager to dict
        self.managers[manager.manager_id] = manager

    def remove_manager(self, manager_id: UUID) -> Union[StreamManager, None]:
        # remove manager from dict and stop it
        try:
            manager = self.managers.pop(manager_id)
            manager.stop("removed by CepticServer")
            return manager
        except KeyError:
            return None

    def remove_all_managers(self) -> list[StreamManager]:
        # remove all managers
        removed_managers = []
        ids = list(self.managers)
        for manager_id in ids:
            removed_managers.append(self.remove_manager(manager_id))
        return removed_managers

    # endregion

    # region Helper Methods
    def check_new_connection_headers(self, request: CepticRequest) -> list[str]:
        errors: list[str] = []
        # check that content length is of allowed length
        # if content length is longer than set max body length, invalid
        if request.content_length and request.content_length > self.settings.body_max:
            errors.append(f"Content-Length ({request.content_length}) exceeds server's allowed max body length of "
                          f"{self.settings.body_max}")
        # check that encoding is recognized and valid
        if request.encoding:
            try:
                EncodeGetter.get(request.encoding)
            except UnknownEncodingException as e:
                errors.append(str(e))
        return errors
    # endregion
