import uuid
import json
import threading
from ceptic import common


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
            ready_to_read, ready_to_write, in_error = common.select_ceptic([self.s], [], [], self.timeout)
            # if ready to read, attempt to get frame from socket
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
        :param new_process_frame: new function
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
    def __init__(self, frame_data, term_data):
        self.id = str(uuid.uuid4())
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
