import uuid
import threading
from collections import deque
from ceptic.common import CepticException, select_ceptic


class StreamManagerException(CepticException):
    """
    Stream-related exception, inherits from CepticException
    """
    def __init__(self, *args):
        CepticException.__init__(self, *args)


class StreamManager(threading.Thread):
    """
    Used for managing a stream of data to and from a socket; input a socket
    """
    REPLACE_NONE = 0
    REPLACE_FRAME = 1
    REPLACE_TERM = 2
    REPLACE_BOTH = 3

    def __init__(self, s, replace_method=REPLACE_BOTH, remove_on_send=False):
        threading.Thread.__init__(self)
        self.s = s
        self.REPLACE_METHOD = replace_method
        # start of stream variables
        self.stream_dictionary = dict()
        self.frames_to_send = deque()
        self.frames_to_read = deque()
        # end of stream variables
        self.dictionary_lock = threading.Lock()
        self.should_run = threading.Event()
        self.timeout = 0.01
        self.remove_on_send = remove_on_send
        self.replace_behavior = {
            self.REPLACE_NONE: self.replace_none,
            self.REPLACE_FRAME: self.replace_frame_only,
            self.REPLACE_TERM: self.replace_term_only,
            self.REPLACE_BOTH: self.replace_both
        }

    def run(self):
        while not self.should_run.isSet():
            ready_to_read, ready_to_write, in_error = select_ceptic([self.s], [], [], self.timeout)
            # if ready to read, attempt to get frame from socket
            for sock in ready_to_read:
                # get frame
                received_frame = StreamFrame().recv_frame(sock)
                # if id exists in dictionary, replace appropriate part of it
                if received_frame.id in self.stream_dictionary:
                    self.replace_behavior[self.REPLACE_METHOD](received_frame)
                else:
                    self.add_frame_to_dict(received_frame)
                # add frame into ready to read deque
                self.frames_to_read.append(received_frame.get_id())
            # if there is new frame(s) to send, attempt to send frame to socket
            if self.is_ready_to_send():
                frame_to_send = self.get_ready_to_send()
                frame_to_send.send_frame(self.s)
                if self.remove_on_send:
                    self.pop(frame_to_send.get_id())

    # start of replace functions
    def replace_none(self, received_frame):
        pass

    def replace_frame_only(self, received_frame):
        self.stream_dictionary[received_frame.get_id()].frame_data = received_frame.frame_data

    def replace_term_only(self, received_frame):
        self.stream_dictionary[received_frame.get_id()].term_data = received_frame.term_data

    def replace_both(self, received_frame):
        self.add_frame_to_dict(received_frame)
    # end of replace functions

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
        return self.stream_dictionary[self.frames_to_send.popleft()]

    def get_ready_to_read(self):
        """
        Return latest frame to read; pops frame id from frames_to_read deque
        :return: latest StreamFrame to read
        """
        return self.stream_dictionary[self.frames_to_read.popleft()]
    #  end of check if ready to read and write functions

    def add_frame_to_dict(self, frame_to_add):
        """
        Add frame to frame dictionary
        :param frame_to_add: StreamFrame to add
        :return: None
        """
        self.stream_dictionary[frame_to_add.get_id()] = frame_to_add

    def pop(self, frame_id):
        """
        Perform pop on stream_dictionary to remove particular frame
        :param frame_id: string uuid mapped to StreamFrame object in dictionary
        :return: StreamFrame object if exists, None if does not
        """
        self.stream_dictionary.pop(frame_id, None)

    def stop(self):
        self.should_run.set()

    def add_frame(self, frame):
        self.stream_dictionary[frame.get_id()] = frame
        self.frames_to_send.append(frame)

    def set_processing_function(self, new_process_frame_function):
        """
        Function used to replace default process_frame function
        :param new_process_frame_function: new function
        :return: None
        """
        self.process_frame = new_process_frame_function

    def process_frame(self, frame):
        """
        Overload this with whatever behavior is necessary
        :param frame: StreamFrame object
        :return: something if you want
        """
        pass


class StreamFrame(object):
    """
    Class for storing data for a frame in a stream
    """
    def __init__(self, frame_data=None, term_data=None, buffer_size=1024000):
        self.id = str(uuid.uuid4())
        self.buffering_size = buffer_size
        self.frame_data = frame_data
        self.term_data = term_data
        self.done = False

    def is_done(self):
        return self.done

    def set_done(self):
        self.done = True

    def unset_done(self):
        self.done = False

    def get_id(self):
        return self.id

    def get_term_data(self):
        return self.term_data

    def __str__(self):
        return self.id

    def recv_frame(self, s):
        """
        Receives StreamFrame data via provided socket
        :param s: socket used to receive frame
        :return: object instance (self)
        """
        raw_frame_data_list = []
        raw_term_data_list = []
        received = 0
        # get StreamFrame UUID
        self.id = str(s.recv(36).strip())
        # get size of frame data and term data
        frame_data_size = int(s.recv(16).strip())
        term_data_size = int(s.recv(16).strip())
        # get frame data
        while received < frame_data_size:
            raw_data_part = s.recv(self.buffering_size)
            # if no data, break out of receiving
            if not raw_data_part:
                break
            else:
                raw_frame_data_list.append(raw_data_part)
                received += len(raw_data_part)
        # get term data
        while received < term_data_size:
            raw_data_part = s.recv(self.buffering_size)
            # if no data, break out of receiving
            if not raw_data_part:
                break
            else:
                raw_term_data_list.append(raw_data_part)
                received += len(raw_data_part)
        # concatenate list items
        self.frame_data = "".join(raw_frame_data_list)
        self.term_data = "".join(raw_term_data_list)
        # return itself
        return self

    def send_frame(self, s):
        """
        Sends StreamFrame data via provided port
        :param s: socket used to send frame
        :return: None
        """
        # check if frame_data and term_data have been provided
        if self.frame_data is None or self.term_data is None:
            raise StreamManagerException("No frame_data and/or term_data in instance to send")
        # get sizes of data to be sent (16 byte blocks)
        frame_data_size = '%16d' % len(self.frame_data)
        term_data_size = '%16d' % len(self.term_data)
        # send id, frame data size, term data size, frame data, and term data (in that order)
        s.sendall(self.id)
        s.sendall(frame_data_size)
        s.sendall(term_data_size)
        s.sendall(self.frame_data)
        s.sendall(self.term_data)
