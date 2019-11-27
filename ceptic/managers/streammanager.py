import uuid
import threading
from multiprocessing import Pipe
from time import sleep
from sys import version_info
from collections import deque
from ceptic.common import CepticException, Timer
from ceptic.network import select_ceptic
from ceptic.encode import EncodeGetter


class StreamManagerException(CepticException):
    """
    General StreamManager-related exception, inherits from CepticException
    """
    pass


class StreamException(StreamManagerException):
    """
    General Stream Exception, inherits from StreamManagerException
    """
    pass


class StreamClosedException(StreamException):
    """
    Stream Closed Exception, inherits from StreamException
    """
    pass


class StreamHandlerStoppedException(StreamClosedException):
    """
    Stream Handler Stopped Exception, inherits from StreamClosedException
    """
    pass


class StreamTimeoutException(StreamException):
    """
    Stream Timeout Exception, inherits from StreamException
    """
    pass


class StreamFrameSizeException(StreamException):
    """
    Stream Frame Size Exception, inherits from StreamException
    """
    pass


class StreamTotalDataSizeException(StreamException):
    """
    Stream Total Data Size Exception, inherits from StreamException
    """
    pass


class StreamManager(threading.Thread):
    """
    Used for managing a stream of data to and from a socket; input a socket
    """

    def __init__(self, s, name, removal_func, settings, is_server=False, conn_func=None, conn_func_args=None):
        threading.Thread.__init__(self)
        self.s = s
        self.name = name
        self.removal_func = removal_func
        self.settings = settings
        self.is_server = is_server
        self.conn_func = conn_func
        self.conn_func_args = conn_func_args
        # control vars
        self.shouldStop = threading.Event()
        self.stop_reason = ""
        self.send_event = threading.Event()
        self.keep_alive_timer = Timer()
        self.isRunning = False
        self.use_processes = False
        self.handler_count = 0
        # timeouts/delays
        self.send_event_timeout = 0.1
        self.clean_delay_time = 0.1
        self.select_timeout = 0.1
        # threads
        self.receive_thread = threading.Thread(target=self.receive_frames)
        self.receive_thread.daemon = True
        self.clean_thread = threading.Thread(target=self.clean_handlers)
        self.clean_thread.daemon = True
        # StreamHandler dict
        self.streams = {}
        self.streams_to_remove = deque()

    def is_handler_limit_reached(self):
        if self.settings["handler_max_count"]:
            if self.handler_count >= self.settings["handler_max_count"]:
                return True
        return False

    def get_handler_count(self):
        return self.handler_count

    def run(self):
        # set start time for keep alive timer
        self.keep_alive_timer.start()
        # start receive thread
        self.isRunning = True
        self.receive_thread.start()
        # start clean thread
        self.clean_thread.start()
        while not self.shouldStop.is_set():
            # iterate through streams
            ready_to_read = self.send_event.wait(self.send_event_timeout)
            if ready_to_read:
                self.send_event.clear()
                streams = list(self.streams)
                for stream_id in streams:
                    stream = self.get_handler(stream_id)
                    # if stream not found, must have been deleted; move on to next one
                    if not stream:
                        continue
                    # while a frame is ready to be sent, send it
                    while stream.is_ready_to_send() and not self.shouldStop.is_set():
                        frame_to_send = stream.get_ready_to_send()
                        frame_to_send.send(self.s)
                        # if sent a close frame, close handler
                        if frame_to_send.is_close():
                            self.streams_to_remove.append(stream_id)
                        elif frame_to_send.is_close_all():
                            self.stop(reason="sending close_all")
                            break
                        # update keep alive time; frame sent, so stream must be active
                        self.keep_alive_timer.update()
        # wait for receive and clean threads to close
        self.receive_thread.join()
        self.clean_thread.join()
        # close any remaining headers
        self.close_all_handlers()
        self.isRunning = False

    def clean_handlers(self):
        while not self.shouldStop.is_set():
            streams = list(self.streams)
            # check if stream has timed out
            for stream_id in streams:
                stream = self.get_handler(stream_id)
                # if stream not found, must have been deleted; move on to next one
                if not stream:
                    continue
                if stream.is_timed_out():
                    self.streams_to_remove.append(stream_id)
                    continue
            # remove timed out streams
            while len(self.streams_to_remove):
                self.close_handler(self.streams_to_remove.popleft())
            sleep(self.clean_delay_time)
            self.check_for_timeout()

    def receive_frames(self):
        while not self.shouldStop.is_set():
            ready_to_read, ready_to_write, in_error = select_ceptic([self.s], [], [], self.select_timeout)
            # if ready to read, attempt to get frame from socket
            for sock in ready_to_read:
                # get frame
                try:
                    received_frame = StreamFrame.from_socket(sock, self.settings["frame_max_size"])
                except (EOFError, StreamFrameSizeException) as e:
                    # stop stream if socket unexpectedly closes or sender does not respect allotted max frame size
                    self.stop(reason="{},{}".format(type(e), str(e)))
                    continue
                # update time for keep alive timer; just received frame, so connection must be alive
                self.keep_alive_timer.update()
                # if keep_alive, ignore; just there to keep connection alive
                if received_frame.is_keep_alive():
                    pass
                # if stream is to be closed, add frame, stop appropriate stream and remove from dict
                if received_frame.is_close():
                    try:
                        self.get_handler(received_frame.get_stream_id()).add_to_read(received_frame)
                    except (KeyError, AttributeError):
                        continue
                    self.streams_to_remove.append(received_frame.stream_id)
                # if all streams are to be closed (including socket), stop all and stop running
                elif received_frame.is_close_all():
                    self.stop("receiving close_all")
                    break
                # if SERVER and if frame of type header, create new stream stream and pass it to conn_handler_func
                elif self.is_server and received_frame.is_header():
                    # if over limit (and limit exists), prepare to close handler after creation
                    should_decline = False
                    if self.is_handler_limit_reached():
                        should_decline = True
                    # create handler and forward received frame
                    stream_id = self.create_handler(stream_id=received_frame.get_stream_id())
                    self.streams[stream_id].add_to_read(received_frame)
                    # handle in new thread
                    conn_thread = threading.Thread(target=self.conn_func, args=(
                        self.streams[stream_id], self.settings, self.conn_func_args))
                    conn_thread.daemon = True
                    conn_thread.start()
                    # close handler if over limit
                    if should_decline:
                        self.get_handler(stream_id).send_close()
                else:
                    try:
                        self.get_handler(received_frame.get_stream_id()).add_to_read(received_frame)
                    except KeyError:
                        continue

    def create_handler(self, stream_id=None):
        if stream_id is None:
            stream_id = str(uuid.uuid4())
        self.streams[stream_id] = StreamHandler(stream_id=stream_id, settings=self.settings, send_event=self.send_event,
                                                use_processes=self.use_processes)
        self.handler_count += 1  # add to handler_count
        return stream_id

    def close_handler(self, stream_id):
        # stop appropriate stream and remove from dict
        stream = self.streams.get(stream_id, None)
        if stream:
            stream.stop()
            self.streams.pop(stream_id)
            self.handler_count -= 1  # subtract from handler_count
            # print("handler with stream_id {} has been closed for manager {}".format(stream_id, self.name))

    def close_all_handlers(self):
        # close all handlers currently stored in streams dict
        stream_ids = list(self.streams)
        for stream_id in stream_ids:
            self.close_handler(stream_id)

    def get_handler(self, stream_id):
        return self.streams.get(stream_id)

    def check_for_timeout(self):
        # if timeout past stream_timeout setting, stop manager
        if self.keep_alive_timer.get_time() > self.settings["stream_timeout"]:
            # print("manager {} timed out".format(self.name))
            self.stop("manager timed out")

    def stop(self, reason=""):
        if reason and not self.shouldStop.is_set():
            self.stop_reason = reason
        self.shouldStop.set()

    def is_stopped(self):
        return self.shouldStop and not self.isRunning

    @classmethod
    def client(cls, socket, name, settings, removal_func):
        return cls(s=socket, name=name, removal_func=removal_func, settings=settings)

    @classmethod
    def server(cls, socket, name, settings, conn_func, conn_func_args, removal_func):
        return cls(s=socket, name=name, removal_func=removal_func, settings=settings, is_server=True,
                   conn_func=conn_func, conn_func_args=conn_func_args)


class StreamHandler(object):
    def __init__(self, stream_id, settings, send_event, use_processes=False):
        self.stream_id = stream_id
        self.settings = settings
        self.send_event = send_event
        self.use_processes = use_processes
        # event for stopping stream
        self.shouldStop = threading.Event()
        self.change_id = None
        # event for received frame
        self.read_or_stop_event = threading.Event()
        # pipes for multiprocessing purposes
        self.manager_pipe = None
        self.handler_pipe = None
        if use_processes:
            self.manager_pipe, self.handler_pipe = Pipe()
        # deques to store frames
        self.frames_to_send = deque()
        self.frames_to_read = deque()
        # keep_alive timer
        self.keep_alive_timer = Timer()
        self.keep_alive_timer.start()
        # compression
        self._encoder = None
        self.set_encode(None)
        # StreamFrameGen
        self.stream_frame_gen = StreamFrameGen(self)

    @property
    def frame_size(self):
        return self.settings["frame_max_size"]

    @property
    def max_header_size(self):
        return self.settings["headers_max_size"]

    @property
    def timeout(self):
        return self.settings["stream_timeout"]

    @property
    def encoder(self):
        return self._encoder

    def set_encode(self, name):
        self._encoder = EncodeGetter.get(name)

    def stop(self):
        self.read_or_stop_event.set()
        self.shouldStop.set()

    def is_stopped(self):
        if self.shouldStop.is_set():
            self.read_or_stop_event.set()
        return self.shouldStop.is_set()

    def is_timed_out(self):
        # if timeout past stream_timeout setting, stop handler
        if self.keep_alive_timer.get_time() > self.settings["stream_timeout"]:
            # print("handler with stream_id {} has timed out".format(self.stream_id))
            return True
        return False

    def send_close(self, data=""):
        try:
            self.send(StreamFrame.create_close(self.stream_id, data=data))
        except StreamHandlerStoppedException:
            pass
        self.stop()

    def send(self, frame):
        """
        Adds frame to send queue
        :param frame: StreamFrame instance
        """
        if self.is_stopped():
            raise StreamHandlerStoppedException("handler is stopped; cannot send frames through a stopped handler")
        self.keep_alive_timer.update()
        if self.use_processes:
            pass
        else:
            frame.data = self.encoder.encode(frame.get_data().encode())
            self.frames_to_send.append(frame)
            self.send_event.set()

    def sendall(self, frames):
        for frame in frames:
            self.send(frame)

    def send_data(self, data):
        self.sendall(self.stream_frame_gen.from_data(data))

    def send_file(self, file_object):
        self.sendall(self.stream_frame_gen.from_file(file_object))

    def add_to_read(self, frame):
        """
        Adds frame to receive queue
        :param frame: StreamFrame instance
        :return: None
        """
        self.keep_alive_timer.update()
        if self.use_processes:
            self.manager_pipe.send(frame)
        else:
            self.frames_to_read.append(frame)
            self.read_or_stop_event.set()

    def get_next_frame(self, timeout=None):
        if timeout is None:
            timeout = self.settings["stream_timeout"]
        expect_frame = True
        # if timeout is 0, then block and wait to get next frame
        if timeout == 0:
            if not self.is_ready_to_read() and not self.is_stopped():
                # wait for read_or_stop_event
                self.read_or_stop_event.wait(None)
            # clear read event
            self.read_or_stop_event.clear()
        # if negative time do not block and immediately return
        elif timeout < 0:
            expect_frame = False
        # wait up to specified time; if no frame received by then, return
        else:
            if not self.is_ready_to_read() and not self.is_stopped():
                # wait for read event
                triggered = self.read_or_stop_event.wait(timeout)
                # if not triggered, must have timed out
                if not triggered:
                    raise StreamTimeoutException("handler {} has timed out getting next frame".format(self.stream_id))
            # clear read event
            self.read_or_stop_event.clear()
        # if handler is stopped and no frames left to read, raise exception
        if self.is_stopped() and not self.is_ready_to_read():
            raise StreamHandlerStoppedException("handler is stopped; cannot receive frames")
        # get frame
        frame = self.get_ready_to_read(expect_frame=expect_frame)
        # if frame is None and not expecting frame to be returned, return the None frame
        if not frame and not expect_frame:
            return frame
        # decompress frame data
        frame.data = self.encoder.decode(frame.get_data())
        # if a close frame, raise exception
        if frame.is_close():
            raise StreamClosedException(frame.get_data())
        return frame

    def get_full_data(self, timeout=None, max_length=None):
        """
        Returns combined data (if applicable) for continued frames until an end frame is encountered
        """
        if timeout is None:
            timeout = self.settings["stream_timeout"]
        # full_data = ""
        frames = []
        total_length = 0
        frame_generator = self.gen_next_frame(timeout)
        for frame in frame_generator:
            if not frame:
                break
            # add data
            frames.append(frame.get_data())
            total_length += len(frame.get_data())
            if max_length and total_length > max_length:  # len(full_data) > max_length:
                raise StreamTotalDataSizeException("total data received has surpassed max_length of {}".format(
                    max_length))
            if frame.is_last():
                break
        # decompress data
        if version_info < (3, 0):  # Python2 code
            full_data = "".join(frames)
        else:  # Python3 code
            full_data = bytes().join(frames)
        return full_data.decode()

    def get_full_header_data(self, timeout=None):
        # length should be no more than allowed header size and max 128 command, 128 endpoint, and 2 \r\n (4 bytes)
        return self.get_full_data(timeout, self.max_header_size + 128 + 128 + 4)

    def get_full_frames(self, timeout=None, max_length=None):
        """
        Returns list of frames (if applicable) for continued frames until an end frame is encountered
        """
        if timeout is None:
            timeout = self.settings["stream_timeout"]
        frames = []
        total_data = 0
        # done = False
        frame_generator = self.gen_next_frame(timeout)
        for frame in frame_generator:
            if not frame:
                break
            # add data
            frames.append(frame)
            total_data += len(frame.get_data())
            if max_length and total_data > max_length:
                raise StreamTotalDataSizeException("total data received has surpassed max_length of {}".format(
                    max_length))
            if frame.is_last():
                break
        return frames

    def gen_next_frame(self, timeout=None):
        while True:
            yield self.get_next_frame(timeout=timeout)

    def gen_next_data(self, timeout=None):
        while True:
            frame = self.get_next_frame(timeout=timeout)
            if not frame:
                break
            yield frame.data

    def gen_full_data(self, timeout=None, max_length=None):
        while True:
            yield self.get_full_data(timeout=timeout, max_length=max_length)

    def gen_full_frames(self, timeout=None, max_length=None):
        while True:
            yield self.get_full_frames(timeout=timeout, max_length=max_length)

    def is_ready_to_send(self):
        """
        Returns if a frame is ready to be sent
        :return: boolean corresponding to if a frame is ready to be sent
        """
        return len(self.frames_to_send) > 0

    def is_ready_to_read(self):
        """
        Returns if a frame is ready to be read
        :return: boolean corresponding to if a frame is ready to be read
        """
        if len(self.frames_to_read) > 0:
            self.read_or_stop_event.set()
        return len(self.frames_to_read) > 0

    def get_ready_to_send(self):
        """
        Return latest frame to send; pops frame id from frames_to_send deque
        :return: latest StreamFrame to send
        """
        try:
            return self.frames_to_send.popleft()
        except IndexError:
            return None

    def get_ready_to_read(self, expect_frame=False):
        """
        Return latest frame to read; pops frame id from frames_to_read deque
        :return: latest StreamFrame to read
        """
        try:
            return self.frames_to_read.popleft()
        except IndexError:
            # workaround for weird Python2 issue, where deque may return positive length before item is readable
            if version_info < (3, 0) and expect_frame:
                # item should be readable shortly, so keep trying to get it
                while True:
                    try:
                        return self.frames_to_read.popleft()
                    except IndexError:
                        pass
            return None

    def get_manager_pipe(self):
        return self.manager_pipe

    def get_handler_pipe(self):
        return self.handler_pipe


class StreamFrameGen(object):
    __slots__ = ("stream", "_frame_size")

    def __init__(self, stream):
        self.stream = stream
        self._frame_size = 0
        self.frame_size = self.stream.frame_size//2

    @property
    def frame_size(self):
        return self._frame_size

    @frame_size.setter
    def frame_size(self, size):
        self._frame_size = size

    @property
    def stream_id(self):
        return self.stream.stream_id

    def from_file(self, file_object):
        """
        Generator for turning contents of file into frames
        :param file_object: readable file instance
        :return: StreamFrame instance of type data
        """
        # get current chunk
        curr_chunk = file_object.read(self.frame_size)
        if not curr_chunk:
            return
        while True:
            # get next chunk from file
            next_chunk = file_object.read(self.frame_size)
            # if nothing was left to read, yield last frame with current chunk
            if not next_chunk:
                yield StreamFrame.create_data_last(self.stream_id, curr_chunk)
                break
            # otherwise, yield continued frame with current chunk
            yield StreamFrame.create_data_continued(self.stream_id, curr_chunk)
            # next chunk becomes current chunk
            curr_chunk = next_chunk

    def from_data(self, data):
        """
        Generator for turning contents of file into frames
        :param data: string or byte array
        :return: StreamFrame instance of type data
        """
        if not data:
            return
        i = 0
        while True:
            # get chunk of data
            chunk = data[i:i + self.frame_size]
            # iterate chunk's starting index
            i += self.frame_size
            # if next chunk will be out of bounds, yield last frame
            if i >= len(data):
                yield StreamFrame.create_data_last(self.stream_id, chunk)
                return
            # otherwise yield continued frame
            yield StreamFrame.create_data_continued(self.stream_id, chunk)


class StreamFrame(object):
    """
    Class for storing data for a frame in a stream
    """
    __slots__ = ("stream_id", "type", "info", "data")

    enum_type = {"data": "0", "header": "1", "keep_alive": "2", "close": "3", "close_all": "4"}
    enum_info = {"continue": "0", "end": "1"}
    null_id = "00000000-0000-0000-0000-000000000000"

    def __init__(self, stream_id=None, frame_type=None, frame_info=None, data=""):
        self.stream_id = stream_id
        self.type = frame_type
        self.info = frame_info
        self.data = data

    def get_stream_id(self):
        """
        Getter for stream_id
        """
        return self.stream_id

    def get_type(self):
        """
        Getter for type
        """
        return self.type

    def get_info(self):
        """
        Getter for info
        """
        return self.info

    def get_data(self):
        """
        Getter for data
        """
        return self.data

    def set_to_header(self):
        """
        Change type to header frame
        :return: None
        """
        self.type = StreamFrame.enum_type["header"]

    def set_to_data(self):
        """
        Change type to data frame
        :return: None
        """
        self.type = StreamFrame.enum_type["data"]

    def send(self, s):
        """
        Send frame through socket instance
        :param s: SocketCeptic instance
        :return: None
        """
        # send stream id
        s.send_raw(self.stream_id)
        # send type
        s.send_raw(self.type)
        # send info
        s.send_raw(self.info)
        # send data if data is set
        if self.data:
            s.sendall(self.data)
        else:
            s.send_raw(format(0, ">16"))

    def is_header(self):
        """
        Checks if instance of frame is header type
        :return: bool
        """
        return self.type == StreamFrame.enum_type["header"]

    def is_data(self):
        """
        Checks if instance of frame is data type
        :return: bool
        """
        return self.type == StreamFrame.enum_type["data"]

    def is_last(self):
        """
        Checks if instance of frame is last (or only) part of data
        :return: bool
        """
        return self.info == StreamFrame.enum_info["end"]

    def is_data_last(self):
        """
        Checks if instance of frame is data type and last (or only) part of data
        :return: bool
        """
        return self.is_data() and self.is_last()

    def is_data_continued(self):
        """
        Checks if instance of frame is data type and is the first (or continuation) of a complete dataset
        :return: bool
        """
        return self.is_data() and self.info == StreamFrame.enum_info["continue"]

    def is_keep_alive(self):
        """
        Checks if instance of frame is keep_alive type
        :return: bool
        """
        return self.type == StreamFrame.enum_type["keep_alive"]

    def is_close(self):
        """
        Checks if instance of frame is close type
        :return: bool
        """
        return self.type == StreamFrame.enum_type["close"]

    def is_close_all(self):
        """
        Checks if instance of frame is close_all type
        :return: bool
        """
        return self.type == StreamFrame.enum_type["close_all"]

    @classmethod
    def from_socket(cls, s, max_data_length):
        """
        Receives frame using socket and returns created instance of frame
        :param s: SocketCeptic instance
        :param max_data_length: int representing maximum allowed data size of frame
        :return: StreamFrame instance
        """
        # get stream id
        stream_id = s.recv_raw(36)
        # get type
        frame_type = s.recv_raw(1)
        # get info
        frame_info = s.recv_raw(1)
        # get data_length
        raw_data_length = None
        try:
            raw_data_length = str(s.recv_raw(16))
            data_length = int(raw_data_length.strip())
        except ValueError:
            raise StreamFrameSizeException("received data_length could not be converted to int: {},{},{},{}".format(
                stream_id, frame_type, frame_info, raw_data_length))
        # if data_length greater than max length, raise exception
        if data_length > max_data_length:
            raise StreamFrameSizeException("data_length ({}) greater than allowed max length of {}".format(
                data_length,
                max_data_length)
            )
        # if data_length not zero, get data
        data = ""
        if data_length > 0:
            data = s.recv_raw(data_length, decode=False)
        return cls(stream_id, frame_type, frame_info, data)

    @classmethod
    def create_header(cls, stream_id, data, frame_info=enum_info["end"]):
        """
        Returns frame initialized as header type; defaults to last frame
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["header"], frame_info, data)

    @classmethod
    def create_data(cls, stream_id, data, frame_info=enum_info["end"]):
        """
        Returns frame initialized as data type; defaults to last frame
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["data"], frame_info, data)

    @classmethod
    def create_data_last(cls, stream_id, data):
        """
        Returns frame initialized as data type, end
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["data"], StreamFrame.enum_info["end"], data)

    @classmethod
    def create_data_continued(cls, stream_id, data):
        """
        Returns frame initialized as data type, continue
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["data"], StreamFrame.enum_info["continue"], data)

    @classmethod
    def create_keep_alive(cls, stream_id):
        """
        Returns frame initialized as keep_alive type
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["keep_alive"], StreamFrame.enum_info["end"])

    @classmethod
    def create_close(cls, stream_id, data=""):
        """
        Returns frame initialized as close type
        :return: StreamFrame instance
        """
        return cls(stream_id, StreamFrame.enum_type["close"], StreamFrame.enum_info["end"], data)

    @classmethod
    def create_close_all(cls):
        """
        Returns frame initialized as close_all type
        :return: StreamFrame instance
        """
        return cls(StreamFrame.null_id, StreamFrame.enum_type["close_all"], StreamFrame.enum_info["end"])
