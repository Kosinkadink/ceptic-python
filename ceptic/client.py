import ssl
import socket
import uuid
from typing import Union, List
from uuid import UUID

from ceptic.common import Constants, SpreadType, CepticException, CepticIOException, CepticStatusCode
from ceptic.net import SocketCeptic
from ceptic.security import SecuritySettings
from ceptic.stream import StreamFrame, StreamHandlerInternal, CepticRequest, CepticResponse, StreamManager, \
    StreamSettings, \
    StreamException, StreamHandler
from ceptic.interfaces import IRemovableManagers


class ClientSettings(object):
    def __init__(self,
                 version: str = "1.0.0",
                 headers_min_size: int = 1024000, headers_max_size: int = 1024000,
                 frame_min_size: int = 1024000, frame_max_size: int = 1024000,
                 body_max: int = 102400000,
                 stream_min_timeout: int = 1, stream_timeout: int = 5,
                 read_buffer_size: int = 102400000, send_buffer_size: int = 102400000,
                 default_port: int = Constants.DEFAULT_PORT):
        self._version = version
        self._headers_min_size = headers_min_size
        self._headers_max_size = headers_max_size
        self._frame_min_size = frame_min_size if frame_min_size < frame_max_size else frame_max_size
        self._frame_max_size = frame_max_size
        if self._frame_min_size < 1000:
            raise ValueError("frame_min_size must be at least 1000; was {}.".format(self._frame_min_size))
        self._body_max = body_max
        self._stream_min_timeout = stream_min_timeout
        self._stream_timeout = stream_timeout
        if send_buffer_size < frame_max_size + StreamFrame.PREFIX_SIZE or \
                read_buffer_size < frame_max_size + StreamFrame.PREFIX_SIZE:
            raise ValueError("send and read buffer sizes must be greater than "
                             "frame_max_size+{} ({}); were {} and {}.".format(StreamFrame.PREFIX_SIZE,
                                                                              frame_max_size + StreamFrame.PREFIX_SIZE,
                                                                              send_buffer_size, read_buffer_size))
        self._send_buffer_size = send_buffer_size
        self._read_buffer_size = read_buffer_size
        self._default_port = default_port

    @property
    def version(self) -> str:
        return self._version

    @property
    def headers_min_size(self) -> int:
        return self._headers_min_size

    @property
    def headers_max_size(self) -> int:
        return self._headers_max_size

    @property
    def frame_min_size(self) -> int:
        return self._frame_min_size

    @property
    def frame_max_size(self) -> int:
        return self._frame_max_size

    @property
    def body_max(self) -> int:
        return self._body_max

    @property
    def stream_min_timeout(self) -> int:
        return self._stream_min_timeout

    @property
    def stream_timeout(self) -> int:
        return self._stream_timeout

    @property
    def read_buffer_size(self) -> int:
        return self._read_buffer_size

    @property
    def send_buffer_size(self) -> int:
        return self._send_buffer_size

    @property
    def default_port(self) -> int:
        return self._default_port


class CepticClient(IRemovableManagers):
    def __init__(self, settings: ClientSettings = None, security: SecuritySettings = None):
        super()
        self.managers: dict[UUID, StreamManager] = dict()
        self.destination_map: dict[str, set[UUID]] = dict()
        self.settings = settings if settings else ClientSettings()
        self.security = security if security else SecuritySettings.client()
        self.ssl_context: Union[ssl.SSLContext, None] = None
        self.setup_security()

    # region Security
    def setup_security(self) -> None:
        """
        Sets up security for CepticClient, or throws SecurityException if something is misconfigured in provided
        SecuritySettings.
        Returns
        -------
        None
        """
        if not self.security.secure:
            return
        # if ssl_context exists on security settings, use it
        if self.security.ssl_context:
            self.ssl_context = self.security.ssl_context
            return
        # otherwise, create default secure settings and customize them if needed
        ssl_context: ssl.SSLContext = ssl.create_default_context()
        # if local_cert present, attempt to load client cert and key
        if self.security.local_cert:
            ssl_context.load_cert_chain(certfile=self.security.local_cert, keyfile=self.security.local_key,
                                        password=self.security.key_password)
        # if remote_cert present, attempt to load server cert
        if self.security.remote_cert or self.security.remote_certs_path:
            ssl_context.load_verify_locations(cafile=self.security.remote_cert,
                                              capath=self.security.remote_certs_path)
        ssl_context.check_hostname = self.security.verify_remote
        self.ssl_context = ssl_context

    @property
    def verify_remote(self):
        return self.security.verify_remote

    @property
    def secure(self):
        return self.security.secure
    # endregion

    # region Connection
    def connect(self, request: CepticRequest, spread: SpreadType = SpreadType.NORMAL) -> CepticResponse:
        # verify and prepare request
        request.verify_and_prepare()
        # create destination based off of host and port
        destination = f"{request.host}:{request.port}"

        manager: StreamManager
        handler: StreamHandlerInternal
        # if normal, check if a manager is available for destination
        if spread == SpreadType.NORMAL:
            manager = self.get_available_manager_for_destination(destination)
            if manager:
                handler = manager.create_handler()
                # connect to server with this handler, returning CepticResponse
                return self.connect_with_handler(handler, request)
        # else if standalone, make stored destination be random UUID to avoid reuse
        else:
            destination += str(uuid.uuid4())
        # create new manager
        manager = self.create_new_manager(request, destination)
        handler = manager.create_handler()
        # connect to server with this handler, returning CepticResponse
        return self.connect_with_handler(handler, request)

    def connect_standalone(self, request: CepticRequest) -> CepticResponse:
        return self.connect(request, spread=SpreadType.STANDALONE)

    def connect_with_handler(self, stream: StreamHandlerInternal, request: CepticRequest) -> CepticResponse:
        try:
            # create frames from request and send
            stream.send_request(request)
            # wait for response
            data = stream.read(max_length=stream.settings.frame_max_size)
            if not data.is_response():
                raise StreamException("No CepticResponse found in response")
            response = data.response
            # if not success status code, close stream and return response
            if not CepticStatusCode.is_success(response.status):
                stream.send_close()
                return response
            # set stream encoding based on request header
            stream.set_encode(request.encoding)
            # send body if content length header is present and greater than 0
            if request.content_length:
                stream.send(request.body)
            # get response
            data = stream.read(stream.settings.frame_max_size)
            if not data.is_response():
                raise StreamException("No CepticResponse found in post-body response")
            response = data.response
            response.stream = StreamHandler(stream)
            # if content length header is present, receive response body
            if response.content_length:
                if response.content_length > self.settings.body_max:
                    raise StreamException(f"Response content length ({response.content_length} is greater than client "
                                          f"allows ({self.settings.body_max}")
                # receive body
                response.body = stream.read_raw(response.content_length)
            # close stream if no Exchange header on response
            if not response.exchange or not request.exchange:
                stream.send_close()
            return response
        except CepticException as e:
            stream.send_close()
            raise
        except Exception as e:
            raise

    def handle_new_connection(self, handler: StreamHandlerInternal) -> None:
        raise NotImplementedError
    # endregion

    # region Stop
    def stop(self):
        self.remove_all_managers()
    # endregion

    # region Managers
    def create_new_manager(self, request: CepticRequest, destination: str) -> StreamManager:
        try:
            raw_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            raw_s.settimeout(5)  # TODO: set all timeouts to match settings
            # s.setblocking(True)
            try:
                raw_s.connect((request.host, request.port))
            except Exception:
                raw_s.close()
                raise
            # connect the socket to the remote endpoint
            try:
                s: Union[SocketCeptic, None] = None
                if self.security.secure:
                    try:
                        ssl_s: ssl.SSLSocket = self.ssl_context.wrap_socket(raw_s, server_side=False)
                        # wrap as SocketCeptic
                        s = SocketCeptic(ssl_s)
                    except ssl.SSLError as e:
                        raise CepticException(f"Could not authenticate as client: {e}") from e
                else:
                    # wrap as SocketCeptic
                    s = SocketCeptic(raw_s)

                # send version
                s.send_raw_str(f"{self.settings.version:>16}")
                # send frame min size
                s.send_raw_str(f"{self.settings.frame_min_size:>16}")
                # send frame max size
                s.send_raw_str(f"{self.settings.frame_max_size:>16}")
                # send headers min size
                s.send_raw_str(f"{self.settings.headers_min_size:>16}")
                # send headers max size
                s.send_raw_str(f"{self.settings.headers_max_size:>16}")
                # send stream min timeout
                s.send_raw_str(f"{self.settings.stream_min_timeout:>4}")
                # send stream timeout
                s.send_raw_str(f"{self.settings.stream_timeout:>4}")
                # get response
                response = s.recv_raw_str(1)
                # if not positive, get additional info and raise exception
                if response != 'y':
                    error_string = s.recv_str(1024)
                    raise CepticIOException(f"Client settings not compatible with server settings: {error_string}")
                # otherwise receive decided values
                server_frame_max_size_str = s.recv_raw_str(16).strip()
                server_header_max_size_str = s.recv_raw_str(16).strip()
                server_stream_timeout_str = s.recv_raw_str(4).strip()
                server_handler_max_count_str = s.recv_raw_str(4).strip()

                # attempt to convert to integers
                frame_max_size: int
                headers_max_size: int
                stream_timeout: int
                handler_max_count: int
                try:
                    frame_max_size = int(server_frame_max_size_str)
                    headers_max_size = int(server_header_max_size_str)
                    stream_timeout = int(server_stream_timeout_str)
                    handler_max_count = int(server_handler_max_count_str)
                except ValueError:
                    raise CepticIOException(f"Server's values were not all integers, could not proceed: "
                                            f"{server_frame_max_size_str},{server_header_max_size_str},"
                                            f"{server_stream_timeout_str},{server_handler_max_count_str}")

                # verify server's chosen values are valid for client
                # TODO: expand checks to check lower bounds
                stream_settings = StreamSettings(self.settings.send_buffer_size, self.settings.read_buffer_size,
                                                 frame_max_size, headers_max_size, stream_timeout, handler_max_count)
                if stream_settings.frame_max_size > self.settings.frame_max_size:
                    raise CepticIOException(f"Server chose frameMaxSize ({stream_settings.frame_max_size}) "
                                            f"higher than client's ({self.settings.frame_max_size})")
                if stream_settings.headers_max_size > self.settings.headers_max_size:
                    raise CepticIOException(f"Server chose headersMaxSize ({stream_settings.headers_max_size}) "
                                            f"higher than client's ({self.settings.headers_max_size})")
                if stream_settings.stream_timeout > self.settings.stream_timeout:
                    raise CepticIOException(f"Server chose streamTimeout ({stream_settings.stream_timeout}) "
                                            f"higher than client's ({self.settings.stream_timeout})")
                # create manager
                manager = StreamManager(s, uuid.uuid4(), destination, stream_settings, self, is_server=False)
                # add and start manager
                self.add_manager(manager)
                manager.start()
                return manager
            except Exception:
                raw_s.close()
                raise
        except Exception:
            raise

    def add_manager(self, manager: StreamManager) -> None:
        manager_set = self.destination_map.get(manager.destination)
        # if manager set already exists for this destination, add manager to that set
        if manager_set:
            manager_set.add(manager.manager_id)
        # otherwise create new set and add to destination map
        else:
            manager_set = set()
            manager_set.add(manager.manager_id)
            self.destination_map[manager.destination] = manager_set
        # add manager to dict
        self.managers[manager.manager_id] = manager

    def get_manager(self, manager_id: UUID) -> Union[StreamManager, None]:
        return self.managers.get(manager_id)

    def get_available_manager_for_destination(self, destination: str) -> Union[StreamManager, None]:
        manager_set = self.destination_map.get(destination)
        # if manager set exists, try to get first manager that isn't saturated with handlers
        if manager_set:
            for manager_id in manager_set:
                manager = self.get_manager(manager_id)
                if manager and not manager.is_stopped() and not manager.is_handler_limit_reached():
                    return manager
        # otherwise return None
        return None

    def remove_manager(self, manager_id: UUID) -> Union[StreamManager, None]:
        # remove manager from managers dict
        try:
            manager = self.managers.pop(manager_id)
            manager.stop("removed by CepticClient")
            # remove manager from manager set in destination map
            manager_set = self.destination_map.get(manager.destination)
            if manager_set:
                try:
                    manager_set.remove(manager.manager_id)
                except KeyError:
                    pass
            return manager
        except KeyError:
            return None

    def remove_all_managers(self) -> list[StreamManager]:
        removed_managers = []
        ids = list(self.managers)
        for manager_id in ids:
            removed_managers.append(self.remove_manager(manager_id))
        return removed_managers
    # endregion
