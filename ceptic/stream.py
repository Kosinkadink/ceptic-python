import json
import traceback
import uuid
from collections import deque

from time import time, sleep
from enum import Enum
from uuid import UUID
from threading import Lock, Event, Thread
from queue import SimpleQueue, Empty as QueueEmptyError
from typing import IO, Generator, Iterable, Union, List

from ceptic.interfaces import IRemovableManagers
from ceptic.common import CepticException, Constants, CepticHeaders, CepticRequestVerifyException, CepticStatusCode
from ceptic.encode import EncodeHandler, EncodeNone, EncodeGetter
from ceptic.net import SocketCeptic, SocketCepticException


# region Exceptions
class StreamException(CepticException):
    """
    Stream-related Ceptic exception.
    """
    pass


class StreamClosedException(StreamException):
    """
    Stream exception caused by stream closing.
    """
    pass


class StreamFrameSizeException(StreamException):
    pass


class StreamHandlerStoppedException(StreamException):
    pass


class StreamTotalDataSizeException(StreamException):
    pass


# endregion


class StreamFrameType(Enum):
    DATA = 0
    HEADER = 1
    RESPONSE = 2
    KEEP_ALIVE = 3
    CLOSE = 4
    CLOSE_ALL = 5

    __slots__ = ("byte_value",)

    def __init__(self, *args):
        self.byte_value = f'{self.value}'.encode()

    def __bytes__(self):
        return self.byte_value


class StreamFrameInfo(Enum):
    CONTINUE = 0
    END = 1

    __slots__ = ("byte_value",)

    def __init__(self, *args):
        self.byte_value = f'{self.value}'.encode()

    def __bytes__(self):
        return self.byte_value


class StreamFrame(object):
    """
    Stores data for a frame in a specific stream.
    """
    __slots__ = ("stream_id", "type", "info", "data")

    NULL_ID = uuid.UUID(int=0)
    ZERO_DATA_LENGTH = "0000000000000000".encode()
    PREFIX_SIZE = 38

    def __init__(self, stream_id: uuid.UUID, frame_type: StreamFrameType, frame_info: StreamFrameInfo,
                 data: bytes = bytearray()) \
            -> None:
        self.stream_id = stream_id
        self.type = frame_type
        self.info = frame_info
        self.data = data

    @property
    def size(self) -> int:
        """
        Returns total size of frame: 36 bytes from UUID, 1 byte from type, 1 byte from info, plus data size.
        """
        return self.PREFIX_SIZE + len(self.data)

    def encode_data(self, encoder: EncodeHandler) -> None:
        self.data = encoder.encode(self.data)

    def decode_data(self, encoder: EncodeHandler) -> None:
        self.data = encoder.decode(self.data)

    def send(self, s: SocketCeptic) -> None:
        """
        Send frame through SocketCeptic instance.
        """
        # send stream id
        s.send_raw(str(self.stream_id).encode())  # TODO: replace with raw bytes
        # send type
        s.send_raw(bytes(self.type))
        # send info
        s.send_raw(bytes(self.info))
        # send data if data is present
        if self.data:
            s.send(self.data)
        else:
            s.send_raw(self.ZERO_DATA_LENGTH)

    @classmethod
    def from_socket(cls, s: SocketCeptic, max_data_length: int) -> 'StreamFrame':
        # get stream id
        raw_string_id = None
        try:
            raw_string_id = s.recv_raw(36).decode()
            stream_id = uuid.UUID(raw_string_id)
        except ValueError as e:
            raise StreamFrameSizeException(f"Received stream id could not be parsed to UUID: {raw_string_id}") from e
        # get type
        raw_frame_type = s.recv_raw(1)
        # get info
        raw_frame_info = s.recv_raw(1)
        # verify type and info are valid
        try:
            frame_type = StreamFrameType(int(raw_frame_type))
        except ValueError as e:
            raise StreamFrameSizeException(f"Received type could not be parsed: {raw_frame_type}") from e
        try:
            frame_info = StreamFrameInfo(int(raw_frame_info))
        except ValueError as e:
            raise StreamFrameSizeException(f"Received info could not be parsed: {raw_frame_info}") from e
        # get data length
        raw_data_length = ""
        try:
            raw_data_length = s.recv_raw(16).decode()
            data_length = int(raw_data_length.strip())
        except ValueError as e:
            raise StreamFrameSizeException(f"Received data length could not be parsed to int: {stream_id},{frame_type},"
                                           f"{frame_info},{raw_data_length}") from e
        # if data length greater than max length, raise exception
        if data_length > max_data_length:
            raise StreamFrameSizeException(f"Data length {data_length} greater than allowed max length of "
                                           f"{max_data_length}")
        # if data length not zero, get data
        data = bytearray()
        if data_length > 0:
            data = s.recv_raw(data_length)
        return cls(stream_id, frame_type, frame_info, data)

    # region Checks
    def is_header(self) -> bool:
        return self.type == StreamFrameType.HEADER

    def is_response(self) -> bool:
        return self.type == StreamFrameType.RESPONSE

    def is_data(self) -> bool:
        return self.type == StreamFrameType.DATA

    def is_keep_alive(self) -> bool:
        return self.type == StreamFrameType.KEEP_ALIVE

    def is_close(self) -> bool:
        return self.type == StreamFrameType.CLOSE

    def is_close_all(self) -> bool:
        return self.type == StreamFrameType.CLOSE_ALL

    def is_last(self) -> bool:
        return self.info == StreamFrameInfo.END

    def is_continued(self) -> bool:
        return self.info == StreamFrameInfo.CONTINUE

    def is_data_last(self) -> bool:
        return self.is_data() and self.is_last()

    def is_data_continued(self) -> bool:
        return self.is_data() and self.is_continued()

    # endregion

    # region Frame Creation
    # Header Frames
    @classmethod
    def create_header(cls, stream_id: uuid.UUID, data: bytes, info: StreamFrameInfo) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.HEADER, info, data)

    @classmethod
    def create_header_last(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_header(stream_id, data, StreamFrameInfo.END)

    @classmethod
    def create_header_continued(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_header(stream_id, data, StreamFrameInfo.CONTINUE)

    # Response Frames
    @classmethod
    def create_response(cls, stream_id: uuid.UUID, data: bytes, info: StreamFrameInfo) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.RESPONSE, info, data)

    @classmethod
    def create_response_last(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_response(stream_id, data, StreamFrameInfo.END)

    @classmethod
    def create_response_continued(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_response(stream_id, data, StreamFrameInfo.CONTINUE)

    # Data Frames
    @classmethod
    def create_data(cls, stream_id: uuid.UUID, data: bytes, info: StreamFrameInfo) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.DATA, info, data)

    @classmethod
    def create_data_last(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_data(stream_id, data, StreamFrameInfo.END)

    @classmethod
    def create_data_continued(cls, stream_id: uuid.UUID, data: bytes) -> 'StreamFrame':
        return cls.create_data(stream_id, data, StreamFrameInfo.CONTINUE)

    # Keep Alive Frames
    @classmethod
    def create_keep_alive(cls, stream_id: uuid.UUID) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.KEEP_ALIVE, StreamFrameInfo.END, bytearray())

    # Close Frames
    @classmethod
    def create_close(cls, stream_id: uuid.UUID, data: bytes = bytearray()) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.CLOSE, StreamFrameInfo.END, data)

    # Close All Frames
    @classmethod
    def create_close_all(cls, stream_id: uuid.UUID) -> 'StreamFrame':
        return cls(stream_id, StreamFrameType.CLOSE_ALL, StreamFrameInfo.END, bytearray())
    # endregion


class StreamSettings(object):
    __slots__ = ("_send_buffer_size", "_read_buffer_size", "_frame_max_size", "_headers_max_size", "_stream_timeout",
                 "_handler_max_count", "verbose")

    def __init__(self, send_buffer_size: int, read_buffer_size: int, frame_max_size: int, headers_max_size: int,
                 stream_timeout: int, handler_max_count: int) -> None:
        self._send_buffer_size = send_buffer_size
        self._read_buffer_size = read_buffer_size
        self._frame_max_size = frame_max_size
        self._headers_max_size = headers_max_size
        self._stream_timeout = stream_timeout
        self._handler_max_count = handler_max_count
        self.verbose = False

    @property
    def send_buffer_size(self) -> int:
        return self._send_buffer_size

    @property
    def read_buffer_size(self) -> int:
        return self._read_buffer_size

    @property
    def frame_max_size(self) -> int:
        return self._frame_max_size

    @property
    def headers_max_size(self) -> int:
        return self._headers_max_size

    @property
    def stream_timeout(self) -> int:
        return self._stream_timeout

    @property
    def handler_max_count(self) -> int:
        return self._handler_max_count


class StreamData(object):
    __slots__ = ("response", "data")

    def __init__(self, response: 'CepticResponse' = None, data: bytes = None):
        self.response = response
        self.data = data

    def is_response(self) -> bool:
        return self.response is not None

    def is_data(self) -> bool:
        return self.data is not None

    def is_empty(self) -> bool:
        return self.response is None and self.data is None


class StreamManager(object):
    """
    Manages streams of data to and from a socket.
    """

    def __init__(self, s: SocketCeptic, manager_id: UUID, destination: str, settings: StreamSettings,
                 removable: IRemovableManagers, is_server: bool) -> None:
        self.s = s
        self.manager_id = manager_id
        self.destination = destination
        self.settings = settings
        self.removable = removable
        self.is_server = is_server
        # send queue - shared by all handlers
        self.send_buffer = SimpleQueue()
        # control vars
        self.should_stop_event = Event()
        self.stop_reason = ""
        self.send_event = Event()
        self.keep_alive_timer = Timer()
        self.existence_timer = Timer()
        self.is_done_running_event = Event()
        self.handler_counter = SafeCounter(0)
        # timeouts/delays
        self.send_event_timeout = 0.1
        self.select_timeout = 0.1
        # threads
        self.send_thread = Thread(target=self.process_sent_frames)
        self.send_thread.daemon = True
        self.receive_thread = Thread(target=self.process_received_frames)
        self.receive_thread.daemon = True
        # dict
        self.streams: dict[uuid.UUID, StreamHandlerInternal] = {}

    def start(self) -> None:
        # start timers
        self.start_timers()
        # start threads
        self.send_thread.start()
        self.receive_thread.start()

    def stop(self, reason="") -> None:
        if not self.should_stop_event.is_set():
            if not self.stop_reason:
                self.stop_reason = reason
            self.should_stop_event.set()

    def is_stopped(self) -> bool:
        return self.should_stop_event.is_set()

    def start_timers(self) -> None:
        self.existence_timer.start()
        self.keep_alive_timer.start()

    def update_keep_alive(self) -> None:
        self.keep_alive_timer.update()

    # region Handler Management
    def is_handler_limit_reached(self) -> bool:
        if self.settings.handler_max_count > 0:
            return len(self.streams) >= self.settings.handler_max_count
        return False

    def create_handler(self, stream_id: uuid.UUID = None) -> Union['StreamHandlerInternal', None]:
        if self.streams.get(stream_id):
            return None
        handler = StreamHandlerInternal(stream_id if stream_id else uuid.uuid4(), self.settings, self.send_buffer)
        self.streams[handler.stream_id] = handler
        return handler

    def remove_handler(self, handler: 'StreamHandlerInternal') -> None:
        handler.stop()
        self.streams.pop(handler.stream_id, None)

    # endregion

    def process_sent_frames(self) -> None:
        try:
            while not self.should_stop_event.is_set():
                # iterate through sent frames
                try:
                    frame: Union[StreamFrame, None] = self.send_buffer.get(block=True, timeout=self.send_event_timeout)
                except QueueEmptyError as e:
                    frame = None
                if frame:
                    # if close all frame, send and then immediately stop manager
                    if frame.is_close_all():
                        # update keep alive; close_all frame about to be sent, so stream must be active
                        self.update_keep_alive()
                        try:
                            frame.send(self.s)
                        except SocketCepticException as e:
                            self.stop("{},{}".format(type(e), str(e)))
                            break
                        self.stop("sending close_all from handler {}".format(frame.stream_id))
                        break
                    # get requesting handler
                    handler = self.streams.get(frame.stream_id)
                    if handler:
                        # update keep alive; frame about to be sent from valid handler, so stream must be active
                        self.update_keep_alive()
                        # decrement sie of handler's send buffer
                        handler.decrement_send_buffer(frame)
                        # try to send frame
                        try:
                            frame.send(self.s)
                        except SocketCepticException as e:
                            # trigger manager to stop if problem with socket
                            self.stop("exception while sending frame: {}".format(e))
                            break
                        # if sent close frame, close handler
                        if frame.is_close():
                            self.remove_handler(handler)
        except Exception as e:
            self.stop(f"Exception occurred in process_sent_frames: {type(e)}:\n{traceback.format_exception(e)}")

    def process_received_frames(self) -> None:
        try:
            while not self.should_stop_event.is_set():
                # try to get frame from socket
                try:
                    frame = StreamFrame.from_socket(self.s, self.settings.frame_max_size)
                except (StreamFrameSizeException, SocketCepticException) as e:
                    self.stop("exception while receiving frame: {}".format(e))
                    break
                # update keep alive timer; just received frame, so connection must be alive
                self.update_keep_alive()
                # if keep alive frame, update keep alive on handler and keep processing;
                # just there to keep connection alive
                if frame.is_keep_alive():
                    handler = self.streams.get(frame.stream_id)
                    if handler:
                        handler.update_keep_alive()
                # if handler is to be closed, add frame and remove handler
                elif frame.is_close():
                    handler = self.streams.get(frame.stream_id)
                    try:
                        if handler:
                            handler.add_to_read(frame)
                            self.remove_handler(handler)
                    except StreamHandlerStoppedException:
                        continue
                # if close all, stop manager
                elif frame.is_close_all():
                    self.stop("received close_all addressed to handler {}".format(frame.stream_id))
                    break
                # if server and header frame, create new handler and pass frame
                elif self.is_server and frame.is_header():
                    handler = self.create_handler(frame.stream_id)
                    # if handler couldn't be created, something is wrong and should stop manager
                    if not handler:
                        self.stop("couldn't create handler - possible duplicate for handler {}".format(frame.stream_id))
                        break
                    if self.is_handler_limit_reached():
                        handler.send_close("Handler limit reached")
                        self.remove_handler(handler)
                        continue
                    try:
                        handler.add_to_read(frame)
                    except StreamHandlerStoppedException:
                        continue
                    # let new thread run removable.handle_new_connection to continue comms with handler
                    handler_thread = Thread(target=self.removable.handle_new_connection, args=(handler,))
                    handler_thread.daemon = True
                    handler_thread.start()
                else:
                    # otherwise try to pass frame to appropriate handler
                    handler = self.streams.get(frame.stream_id)
                    if handler:
                        try:
                            handler.add_to_read(frame)
                        except StreamHandlerStoppedException:
                            pass
        except Exception as e:
            self.stop(f"Exception occurred in process_received_frames: {type(e)}:\n{traceback.format_exception(e)}")


class StreamHandler(object):
    def __init__(self, wrapped: 'StreamHandlerInternal') -> None:
        self.wrapped = wrapped

    @property
    def settings(self) -> StreamSettings:
        return self.wrapped.settings

    @property
    def stream_id(self) -> uuid.UUID:
        return self.wrapped.stream_id

    def is_stopped(self) -> bool:
        return self.wrapped.is_stopped()

    def send(self, data: bytes) -> None:
        self.wrapped.send_data(data)

    def send_response(self, response: 'CepticResponse') -> None:
        self.wrapped.send_response(response)

    def send_close(self, data: Union[bytes, str] = bytearray()):
        self.wrapped.send_close(data)

    def read(self, max_length: int, timeout: float = None) -> StreamData:
        return self.wrapped.read(max_length=max_length, timeout=timeout)

    def read_raw(self, max_length: int, timeout: float = None) -> bytes:
        return self.wrapped.read_raw(max_length=max_length, timeout=timeout)


class StreamHandlerInternal(object):
    def __init__(self, stream_id: uuid.UUID, settings: StreamSettings, send_buffer: SimpleQueue) -> None:
        self.stream_id = stream_id
        self.settings = settings
        # event for stopping stream
        self.should_stop_event = Event()
        # event for received frame
        self.read_or_stop_event = Event()
        # deques to store frames
        self.frames_to_send = send_buffer
        self.frames_to_read = deque()
        # buffer sizes
        self.send_buffer_counter = SafeCounter()
        self.read_buffer_counter = SafeCounter()
        # events for awaiting decrease of buffer size
        self.send_buffer_ready_or_stop = Event()
        self.read_buffer_ready_or_stop = Event()
        self.buffer_wait_timeout = 0.1
        # handler existence timer
        self.existence_timer = Timer()
        self.existence_timer.start()
        # keep alive timer
        self.keep_alive_timer = Timer()
        self.keep_alive_timer.start()
        # encoding
        self._encoder = EncodeHandler([EncodeNone])
        # stream frame generation
        self.stream_frame_gen = StreamFrameGen(self)

    @property
    def encoder(self) -> EncodeHandler:
        return self._encoder

    @encoder.setter
    def encoder(self, encoder: EncodeHandler) -> None:
        self._encoder = encoder

    def stop(self):
        self.read_or_stop_event.set()
        self.send_buffer_ready_or_stop.set()
        self.read_buffer_ready_or_stop.set()
        self.should_stop_event.set()

    def set_encode(self, encoding_str: str):
        self.encoder = EncodeGetter.get(encoding_str)

    def is_stopped(self):
        if self.should_stop_event.is_set():
            self.read_or_stop_event.set()
        return self.should_stop_event.is_set()

    def is_timed_out(self):
        # if timeout past stream_timeout setting, stop handler
        if self.keep_alive_timer.get_time_current() > self.settings.stream_timeout:
            return True
        return False

    def update_keep_alive(self):
        self.keep_alive_timer.update()

    # region Buffer Checks
    def is_send_buffer_full(self) -> bool:
        return self.send_buffer_counter.value > self.settings.send_buffer_size

    def is_read_buffer_full(self) -> bool:
        return self.read_buffer_counter.value > self.settings.read_buffer_size

    def is_ready_to_read(self) -> bool:
        """
        Returns if a frame is ready to be read. Triggers read_or_stop_event if ready.
        """
        ready = len(self.frames_to_read) > 0
        if ready:
            self.read_or_stop_event.set()
        return ready

    def increment_send_buffer(self, frame: StreamFrame) -> None:
        self.send_buffer_counter.increment(frame.size)

    def decrement_send_buffer(self, frame: StreamFrame) -> None:
        self.send_buffer_counter.decrement(frame.size)
        # potentially flag that send buffer is not full, if currently awaiting event
        if not self.is_send_buffer_full() and not self.send_buffer_ready_or_stop.is_set():
            self.send_buffer_ready_or_stop.set()

    def increment_read_buffer(self, frame: StreamFrame) -> None:
        self.read_buffer_counter.increment(frame.size)

    def decrement_read_buffer(self, frame: StreamFrame) -> None:
        self.read_buffer_counter.decrement(frame.size)
        # potentially flag that read buffer is not full, if currently awaiting event
        if not self.is_read_buffer_full() and not self.read_buffer_ready_or_stop.is_set():
            self.read_buffer_ready_or_stop.set()

    # endregion

    def send_close(self, data: Union[bytes, str] = bytearray()) -> None:
        """
        Send a close frame with optional data content (not to exceed half of frame size) and stop handler.
        Does not block unless queue full.
        """
        if isinstance(data, str):
            data = data.encode()
        try:
            self.send_frame(StreamFrame.create_close(self.stream_id, data))
        except StreamHandlerStoppedException:
            pass
        self.stop()

    def send_frame(self, frame: StreamFrame) -> None:
        """
        Add StreamFrame to send queue. Does not block unless queue full.
        """
        if self.is_stopped():
            raise StreamHandlerStoppedException("Handler is stopped; cannot send frames through a stopped handler.")
        self.keep_alive_timer.update()
        frame.encode_data(self.encoder)
        # check if enough room in buffer
        self.increment_send_buffer(frame)
        if self.is_send_buffer_full():
            # wait until buffer is decreased enough to fit new frame
            self.send_buffer_ready_or_stop.clear()
            while self.is_send_buffer_full() and not self.is_stopped():
                ready = self.send_buffer_ready_or_stop.wait(self.buffer_wait_timeout)
                if ready:
                    break
        self.frames_to_send.put(frame)

    def send_frames(self, frames: Iterable) -> None:
        """
        Send all frames in iterable. Should typically be used with a generator. Does not block unless queue full.
        """
        for frame in frames:
            self.send_frame(frame)

    def send_data(self, data: bytes) -> None:
        """
        Send all data - will use a generator to iterate through the data and sends StreamFrames. Does not block unless
        queue full.
        """
        self.send(data)

    def send(self, data: bytes, is_first_header: bool = False, is_response: bool = False) -> None:
        """
        Send all data - will use a generator to iterate through the data and sends StreamFrames. Does not block unless
        queue full.
        """
        self.send_frames(self.stream_frame_gen.from_data(data, is_first_header, is_response))

    def send_request(self, request: 'CepticRequest') -> None:
        """
        Send request as data converted into StreamFrames added to send buffer.
        """
        self.send(request.get_data(), is_first_header=True)

    def send_response(self, response: 'CepticResponse') -> None:
        """
        Send CepticResponse object. Does not block.
        """
        self.send(response.get_data(), is_response=True)

    def send_file(self, file_object: IO):
        """
        Send all data in a readable IO - will use a generator to iterate through the data and sends StreamFrames.
        Does not block unless queue full.
        """
        self.send_frames(self.stream_frame_gen.from_file(file_object))

    def add_to_read(self, frame: StreamFrame) -> None:
        """
        Adds frame to receive queue.
        """
        self.keep_alive_timer.update()
        # check if enough room in buffer
        self.increment_read_buffer(frame)  # TODO: review this order of actions
        if self.is_read_buffer_full():
            # wait until buffer is decreased enough to fit new frame
            self.read_buffer_ready_or_stop.clear()
            while self.is_read_buffer_full() and not self.is_stopped():
                ready = self.read_buffer_ready_or_stop.wait(self.buffer_wait_timeout)
                if ready:
                    break
        self.frames_to_read.append(frame)
        self.read_or_stop_event.set()

    def read_next_frame(self, timeout: float) -> Union[StreamFrame, None]:
        # if timeout is less than 0, then block and wait to get next frame (up to stream timeout)
        if timeout < 0:
            if not self.is_ready_to_read() and not self.is_stopped():
                # wait for ready or stop event
                self.read_or_stop_event.wait(self.settings.stream_timeout)
            # clear read event
            self.read_or_stop_event.clear()
        # if timeout is greater than 0, wait up to timeout; if no frame received by then, return
        elif timeout > 0:
            triggered = True
            if not self.is_ready_to_read() and not self.is_stopped():
                # wait for read event
                triggered = self.read_or_stop_event.wait(timeout)
            # clear read event if triggered
            if triggered:
                self.read_or_stop_event.clear()
        # if timeout is 0, do not block and immediately attempt to read
        # if handler is stopped and no frames left to read, raise exception
        if self.is_stopped() and not self.is_ready_to_read():
            raise StreamHandlerStoppedException("Handler is stopped; cannot receive frames.")
        # get frame
        frame = self.get_ready_to_read()
        # if frame is None, return the None frame
        if not frame:
            return frame
        # decode frame data
        frame.decode_data(self.encoder)
        # if a close frame, raise exception
        if frame.is_close():
            raise StreamClosedException(frame.data.decode())
        return frame

    def read_full_data(self, timeout: float, max_length: int, convert_response: bool) -> StreamData:
        """
        Returns combined data (if applicable) for continued frames until an end frame is encountered,
        or a CepticResponse instance
        :param timeout: timeout time (uses stream_timeout setting by default)
        :param max_length: max length; allows throwing StreamTotalDataSizeException if exceeds limit
        :param convert_response: if true (default), will convert data to CepticResponse
        if any frames encountered are of type RESPONSE
        """
        if timeout is None:
            timeout = self.settings.stream_timeout
        frames = []
        total_length = 0
        frame_generator = self.generate_next_frame(timeout)
        is_response = False
        for frame in frame_generator:
            if not frame:
                break
            # add data
            frames.append(frame.data)
            total_length += len(frame.data)
            if max_length and total_length > max_length:
                raise StreamTotalDataSizeException(f"Total data received has surpassed max length of {max_length}")
            if frame.is_response():
                is_response = True
            if frame.is_last():
                break
        # combine data
        full_data = bytes().join(frames)
        if convert_response and is_response:
            return StreamData(response=CepticResponse.from_data(full_data))
        return StreamData(data=full_data)

    def read_header_data(self, timeout: float = None) -> StreamData:
        # length should be no more than: headers max size + command + endpoint + 2x\r\n (4 bytes)
        return self.read_full_data(timeout, self.settings.headers_max_size + Constants.COMMAND_LENGTH
                                   + Constants.ENDPOINT_LENGTH + 4, False)

    def read(self, max_length: int, timeout: float = None) -> StreamData:
        """
        Returns combined data (if applicable) for continued frames until an end frame is encountered,
        or a CepticResponse instance
        :param timeout: optional timeout time (uses stream_timeout setting by default)
        :param max_length: optional max length; allows throwing StreamTotalDataSizeException if exceeds limit
        """
        if timeout is None:
            timeout = self.settings.stream_timeout
        return self.read_full_data(timeout, max_length, convert_response=True)

    def read_raw(self, max_length: int, timeout: float = None) -> bytes:
        """
        Returns raw data for continued frames until an end frame is encountered
        :param timeout: optional timeout time (uses stream_timeout setting by default)
        :param max_length: optional max length; allows throwing StreamTotalDataSizeException if exceeds limit
        """
        if timeout is None:
            timeout = self.settings.stream_timeout
        return self.read_full_data(timeout, max_length, convert_response=False).data

    def read_full_frames(self, timeout: float = None, max_length: int = None) -> list[StreamFrame]:
        """
        Returns list of frames (if applicable) for continued frames until an end frame is encountered
        """
        if timeout is None:
            timeout = self.settings.stream_timeout
        frames = []
        total_data = 0
        frame_generator = self.generate_next_frame(timeout)
        for frame in frame_generator:
            if not frame:
                break
            # add data
            frames.append(frame)
            total_data += len(frame.data)
            if max_length and total_data > max_length:
                raise StreamTotalDataSizeException(f"Total data received has surpassed max_length of {max_length}")
            if frame.is_last():
                break
        return frames

    # region Generators
    def generate_next_frame(self, timeout: float) -> Generator[StreamFrame, None, None]:
        while True:
            yield self.read_next_frame(timeout)

    def generate_next_data(self, timeout: float) -> Generator[bytes, None, None]:
        while True:
            frame = self.read_next_frame(timeout)
            if not frame:
                break
            yield frame.data

    def generate_full_data(self, timeout: float = None, max_length: int = 0) -> Generator[bytes, None, None]:
        """
        Generator for getting data frame-by-frame until an end frame is encountered
        :param timeout: timeout time (uses stream_timeout setting by default)
        :param max_length: optional max length; allows throwing exception if exceeds limit
        """
        if timeout is None:
            timeout = self.settings.stream_timeout
        total_length = 0
        frame_generator = self.generate_next_frame(timeout)
        for frame in frame_generator:
            if not frame:
                break
            # add data
            yield frame.data
            total_length += len(frame.data)
            if max_length and total_length > max_length:
                raise StreamTotalDataSizeException(f"Total data received has surpassed max length of {max_length}")
            if frame.is_last():
                break

    def generate_next_full_data(self, timeout: float = None, max_length: int = None) -> Generator[bytes, None, None]:
        while True:
            yield self.read_full_data(timeout, max_length, False)

    def generate_next_full_frames(self, timeout: float = None, max_length: int = None) -> Generator:
        while True:
            yield self.read_full_frames(timeout, max_length)

    # endregion

    def get_ready_to_read(self) -> Union[StreamFrame, None]:
        """
        Return latest frame to read; pops frame id from frames to read deque.
        """
        frame: Union[StreamFrame, None] = None
        try:
            frame = self.frames_to_read.popleft()
            return frame
        except IndexError:
            return None
        finally:
            # if frame was taken from queue, decrement deque size
            if frame:
                self.decrement_read_buffer(frame)


class StreamFrameGen(object):
    __slots__ = ("stream", "_frame_size")

    def __init__(self, stream: StreamHandlerInternal):
        self.stream = stream
        self._frame_size = 0
        self.frame_size = self.stream.settings.frame_max_size // 2

    @property
    def frame_size(self) -> int:
        return self._frame_size

    @frame_size.setter
    def frame_size(self, size: int) -> None:
        self._frame_size = size

    @property
    def stream_id(self) -> uuid.UUID:
        return self.stream.stream_id

    def from_data(self, data: bytes, is_first_header: bool = False, is_response: bool = False) \
            -> Generator[StreamFrame, None, None]:
        """
        Generator for converting bytes into StreamFrames.
        """
        if not data:
            return
        i = 0
        while True:
            # get chunk of data
            chunk = data[i:i + self.frame_size]
            # iterate chunk's starting index
            i += self.frame_size
            # if next chunk will be out of bounds, yield final frame
            if i >= len(data):
                if is_first_header:
                    is_first_header = False
                    yield StreamFrame.create_header_last(self.stream_id, chunk)
                else:
                    if is_response:
                        is_response = False
                        yield StreamFrame.create_response_last(self.stream_id, chunk)
                    else:
                        yield StreamFrame.create_data_last(self.stream_id, chunk)
                return
            # otherwise yield continued frame
            if is_first_header:
                is_first_header = False
                yield StreamFrame.create_header_continued(self.stream_id, chunk)
            else:
                if is_response:
                    is_response = False
                    yield StreamFrame.create_response_continued(self.stream_id, chunk)
                else:
                    yield StreamFrame.create_data_continued(self.stream_id, chunk)

    def from_file(self, file_object: IO) -> Generator[StreamFrame, None, None]:
        """
        Generator for converting IO into StreamFrames.
        :param file_object: readable IO
        """
        # get current chunk
        current_chunk = file_object.read(self.frame_size)
        if not current_chunk:
            return
        while True:
            # get next chunk from file
            next_chunk = file_object.read(self.frame_size)
            # if nothing was left to read, yield final frame with current chunk
            if not next_chunk:
                yield StreamFrame.create_data_last(self.stream_id, current_chunk)
                break
            # otherwise, yield continued frame with current chunk
            yield StreamFrame.create_data_continued(self.stream_id, current_chunk)
            # next chunk becomes current chunk
            current_chunk = next_chunk


class CepticRequest(CepticHeaders):
    def __init__(self, command: str, url: str, body: bytes = None, headers: dict = None) -> None:
        super().__init__(headers)
        self.command = command
        self.url = url
        self.endpoint = ""
        self.body = body
        self.stream: Union[StreamHandler, None] = None
        self.host = ""
        self.port = Constants.DEFAULT_PORT
        self.values: Union[dict[str, str], None] = None
        self.queryparams: Union[dict[str, str], None] = None
        self.querystring: str = ""

    @staticmethod
    def create_with_endpoint(command: str, endpoint: str, body: bytes = None, headers: dict = None) -> 'CepticRequest':
        request = CepticRequest(command, "", body, headers=headers)
        request.endpoint = endpoint
        return request

    @property
    def body(self) -> bytearray:
        return self._body

    @body.setter
    def body(self, value: bytes):
        if not value:
            value = bytearray()
        else:
            self.content_length = len(value)
        self._body = value

    def verify_and_prepare(self) -> None:
        # check that command isn't empty
        if not self.command:
            raise CepticRequestVerifyException("Command cannot be empty.")
        # check that url isn't empty
        if not self.url:
            raise CepticRequestVerifyException("Url cannot be empty.")
        # don't redo verification is already satisfied
        if self.host and self.endpoint:
            return
        # extract request components from url
        components = self.url.split("/", 1)
        # set endpoint
        if len(components) < 2 or not components[1]:
            self.endpoint = "/"
        else:
            self.endpoint = components[1]
        # extract host and port from first component
        elements = components[0].split(":", 1)
        self.host = elements[0]
        if len(elements) > 1:
            try:
                self.port = int(elements[1])
            except ValueError as e:
                raise CepticRequestVerifyException(f"Port must be an integer, not {elements[1]}.") from e

    def get_data(self) -> bytes:
        return f"{self.command}\r\n{self.endpoint}\r\n{json.dumps(self.headers)}".encode()

    @classmethod
    def from_data(cls, data: bytes) -> 'CepticRequest':
        command, endpoint, json_headers = data.decode().split("\r\n")
        return cls.create_with_endpoint(command, endpoint, headers=json.loads(json_headers))

    def begin_exchange(self) -> Union[StreamHandler, None]:
        response = CepticResponse(CepticStatusCode.EXCHANGE_START)
        response.exchange = True
        if self.stream and not self.stream.is_stopped():
            try:
                if not self.exchange:
                    self.stream.send_response(CepticResponse(CepticStatusCode.MISSING_EXCHANGE))
                    if self.stream.settings.verbose:
                        print("Request did not have required Exchange header")
                    return None
                self.stream.send_response(response)
            except StreamException as e:
                if self.stream.settings.verbose:
                    print(f"StreamException {type(e)} while trying to begin_exchange: {e}")
                return None
            return self.stream
        return None


class CepticResponse(CepticHeaders):
    def __init__(self, status: Union[CepticStatusCode, int],
                 body: Union[bytes, None] = None, headers: Union[dict, None] = None,
                 errors: Union[List, None] = None, stream: Union[StreamHandler, None] = None) -> None:
        super().__init__(headers)
        self.status = status
        self.body = body
        if errors:
            self.errors = errors
        self.stream = stream

    @property
    def body(self) -> bytearray:
        return self._body

    @body.setter
    def body(self, value: bytes):
        if not value:
            value = bytearray()
        else:
            self.content_length = len(value)
        self._body = value

    def get_data(self) -> bytes:
        return f"{self.status}\r\n{json.dumps(self.headers)}".encode()

    @classmethod
    def from_data(cls, data: bytes) -> 'CepticResponse':
        status, json_headers = data.decode().split("\r\n")
        if json_headers:
            return cls(int(status), headers=json.loads(json_headers))
        return cls(status)

    def __str__(self):
        return f"{self.status},{self.headers},{self.body}"


class Timer(object):
    __slots__ = ("start_time", "end_time")

    def __init__(self) -> None:
        self.start_time = 0.0
        self.end_time = 0.0

    def start(self) -> None:
        self.start_time = time()

    def update(self) -> None:
        self.start()

    def stop(self) -> float:
        self.end_time = time()
        return self.get_time_diff()

    def get_time_diff(self) -> float:
        return self.end_time - self.start_time

    def get_time_current(self) -> float:
        return time() - self.start_time


class SafeCounter(object):
    __slots__ = ("value", "_lock")

    def __init__(self, value=0) -> None:
        self.value = value
        self._lock = Lock()

    def increment(self, value=1) -> None:
        with self._lock:
            self.value += value

    def decrement(self, value=1) -> None:
        with self._lock:
            self.value -= value
