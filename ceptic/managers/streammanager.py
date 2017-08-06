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
    def __init__(self, s):
        threading.Thread.__init__(self)
        self.s = s
        self.stream_dictionary = {}
        self.to_send_queue = []
        self.dictionary_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.should_run = threading.Event()
        self.timeout = 0.01

    def run(self):
        if not self.should_run.isSet():
            ready_to_read, ready_to_write, in_error = select_ceptic([self.s], [], [], self.timeout)
            # if ready to read, attempt to get frame from socket
            for sock in ready_to_read:
                # get frame
                receivedFrame = StreamFrame().recv_frame(sock)
            # if there is new frame(s) to send, attempt to send frame to socket

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
    def __init__(self, frame_data=None, term_data=None):
        self.id = str(uuid.uuid4())
        self.buffering_size = 1024000
        self.frame_data = frame_data
        self.term_data = term_data
        self.done = False

    def is_done(self):
        return self.done

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

    def send_frame(self,s):
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
        # send frame data size, term data size, frame data, and term data (in that order)
        s.sendall(frame_data_size)
        s.sendall(term_data_size)
        s.sendall(self.frame_data)
        s.sendall(self.term_data)
