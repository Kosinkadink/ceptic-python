import uuid
import threading
from ceptic.common import CepticException, select_ceptic


class StreamManagerException(CepticException):
    """
    Stream-related exception, inherits from CepticException
    """
    def __init(self, *args):
        CepticException.__init__(self, *args)


class StreamManager(threading.Thread):
    """
    Used for managing a stream of data to and from a socket; input a socket
    """
    REPLACE_NONE = 0
    REPLACE_FRAME = 1
    REPLACE_TERM = 2
    REPLACE_BOTH = 3

    def __init__(self, s, replace_method=REPLACE_TERM):
        threading.Thread.__init__(self)
        self.s = s
        self.REPLACE_METHOD = replace_method
        self.stream_dictionary = {}
        self.to_send_queue = []
        self.dictionary_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.should_run = threading.Event()
        self.timeout = 0.01
        self.replace_behavior = {
            self.REPLACE_NONE: self.replace_none,
            self.REPLACE_FRAME: self.replace_frame_only,
            self.REPLACE_TERM: self.replace_term_only,
            self.REPLACE_BOTH: self.replace_both
        }

    def run(self):
        if not self.should_run.isSet():
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
            # if there is new frame(s) to send, attempt to send frame to socket

    def add_frame_to_dict(self, frame_to_add):
        self.stream_dictionary[frame_to_add.id] = frame_to_add

    def replace_none(self, received_frame):
        pass

    def replace_frame_only(self, received_frame):
        self.stream_dictionary[received_frame.id].frame_data = received_frame.frame_data

    def replace_term_only(self, received_frame):
        self.stream_dictionary[received_frame].term_data = received_frame.term_data

    def replace_both(self, received_frame):
        self.add_frame_to_dict(received_frame)

    def pop(self, frame_id):
        """
        Perform pop on stream_dictionary to remove particular frame
        :param frame_id: string uuid mapped to StreamFrame object in dictionary
        :return: StreamFrame object if exists, None if does not
        """
        self.dictionary_lock.acquire()
        self.stream_dictionary.pop(frame_id, None)
        self.dictionary_lock.release()

    def stop(self):
        self.should_run.set()

    def add_frame(self, frame):
        self.queue_lock.acquire()
        self.to_send_queue.append(frame)
        self.queue_lock.release()

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
