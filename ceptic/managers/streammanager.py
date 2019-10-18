import uuid
import threading
from multiprocessing import Pipe
from time import time
from sys import version_info
from collections import deque
from ceptic.common import CepticException
from ceptic.network import select_ceptic


class StreamManagerException(CepticException):
    """
    Stream-related exception, inherits from CepticException
    """
    pass


class StreamManager(threading.Thread):
    """
    Used for managing a stream of data to and from a socket; input a socket
    """
    def __init__(self, s, is_server=False):
        self.s = s
        # control vars
        self.should_stop = threading.Event()
        self.use_processes = False
        self.timeout = 0.001
        self.is_server = is_server
        # special case deque
        self.special_frames_to_send = deque()
        # threads
        self.receive_thread = threading.Thread(target=self.receive_frames)
        self.receive_thread.daemon=True
        # StreamHandler dict
        streams = {}

    def run(self):
        # start receive thread
        receive_thread.start()
        while not self.should_stop.is_set():
            # check if any special frames are to be sent
            # iterate through streams
            for stream_id in streams:
                stream = streams[stream_id]
                # if a frame is ready to be sent, send it
                if stream.is_ready_to_send():
                    frame_to_send = self.get_ready_to_send()
                    frame_to_send.send(self.s)
        # wait for receive_thread to fully close
        self.receive_thread.join()

    def receive_frames(self):
        while not self.should_stop.is_set():
            ready_to_read, ready_to_write, in_error = select_ceptic([self.s], [], [], self.timeout)
            # if ready to read, attempt to get frame from socket
            for sock in ready_to_read:
                # get frame
                try:
                    received_frame = StreamFrame.from_socket(self.s)
                except EOFError:
                    self.stop()
                    continue
                # if keep_alive, ignore; just there to keep connection alive
                if received_frame.type == StreamFrame.enum_type["keep_alive"]:
                    pass
                # if stream is to be closed, stop appropriate handler and remove from dict
                if received_frame.type == StreamFrame.enum_type["close"]:
                    streams[received_frame.stream_id].stop()
                    streams.pop(received_frame.stream_id)
                # if all streams are to be closed (including socket), stop all and stop running
                elif received_frame.type == StreamFrame.enum_type["close_all"]:
                    pass
                # if SERVER and if frame of type header, create new stream handler            
                elif self.is_server and received_frame.type == StreamFrame.enum_type["header"]:
                    stream_id = create_handler()
                    received_frame.stream_id = stream_id
                    streams[stream_id].recv(received_frame)

    def start_new_client_stream(self, frame):
        # make sure frame is of type header
        if frame.type != StreamFrame.enum_type["header"]:
            raise StreamManagerException("frame to start new stream must be of type 'header'; was {} instead".format(frame.type))

    def create_handler(self):
        stream_id = str(uuid.uuid4())
        self.streams[stream_id] = StreamHandler(stream_id=stream_id,use_processes=self.use_processes)
        return stream_id

    def stop(self):
        self.should_stop.set()

    def close(self):
        self.stop()

    def is_running(self):
        return not self.should_stop.is_set()


class StreamHandler(object):
    def __init__(self, stream_id=None, use_processes=False):
        self.should_stop = threading.Event()
        if not stream_id:
            self.stream_id = str(uuid.uuid4())
        else:
            self.stream_id = stream_id
        self.manager_pipe = None
        self.handler_pipe = None
        if use_processes:
            self.manager_pipe,self.handler_pipe = Pipe()
        self.frames_to_send = deque()
        self.frames_to_read = deque()

    def run(self):
        pass

    def stop(self):
        self.should_stop.set()
        self.send(StreamFrame.close(self.stream_id))

    def close(self):
        self.stop()

    def send(self, frame):
        if self.use_processes:
            pass
        else:
            self.frames_to_send.append(frame)

    def recv(self, frame):
        if self.use_processes:
            self.manager_pipe.send(frame)
        else:
            self.frames_to_read.append(frame)

    # start of check if ready to read and write functions
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

    def get_ready_to_read(self):
        """
        Return latest frame to read; pops frame id from frames_to_read deque
        :return: latest StreamFrame to read
        """
        try:
            return self.frames_to_read.popleft()
        except IndexError:
            return None
    #  end of check if ready to read and write functions

    def get_manager_pipe(self):
        return self.manager_pipe

    def get_handler_pipe(self):
        return self.handler_pipe


class StreamFrame(object):
    """
    Class for storing data for a frame in a stream
    """
    enum_type = {"header":"0","data":"1","keep_alive":"2","close":"3","close_all":"4"}
    enum_info = {"continue":"0","end":"1"}
    null_id = "00000000-0000-0000-0000-000000000000"

    def __init__(self, stream_id, frame_type, frame_info, data):
        self.stream_id = None
        self.type = None
        self.info = None
        self.data = None

    def send(self, s):
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
            s.send_raw('%16d' % 0)
        
    @classmethod
    def from_socket(cls, s):
        # get stream id
        stream_id = s.recv_raw(36)
        # get type
        frame_type = s.recv_raw(1)
        # get info
        frame_info = s.recv_raw(1)
        # get datalength
        data_length = int(str(s.recv_raw(16).strip()))
        # if datalength not zero, get data
        data = None
        if datalength > 0:
            data = s.recv_raw(data_length)
        return cls(stream_id, frame_type, frame_info, data)

    @classmethod
    def header(cls, stream_id, data):
        return cls(stream_id, self.enum_type["header"], self.enum_info["end"], data)

    @classmethod
    def data(cls, stream_id, data, frame_info=enum_info["continue"]):
        return cls(stream_id, self.enum_type["data"], frame_info, data)

    @classmethod
    def data_last(cls, stream_id, data):
        return cls(stream_id, self.enum_type["data"], self.enum_type["end"], data)

    @classmethod
    def keep_alive(cls, stream_id):
        return cls(stream_id, self.enum_type["keep_alive"], self.enum_info["end"], None)

    @classmethod
    def close(cls, stream_id):
        return cls(stream_id, self.enum_type["close"], self.enum_info["end"], None)

    @classmethod
    def close_all(cls, stream_id):
        return cls(self.null_id, self.enum_type["close_all"], self.enum_info["end"], None)
