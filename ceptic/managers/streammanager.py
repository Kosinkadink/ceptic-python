import uuid
import threading
from collections import deque
from ceptic.common import CepticException, select_ceptic


class StreamManagerException(CepticException):
    """
    Stream-related exception, inherits from CepticException
    """
    pass


class StreamManager(threading.Thread):
    """
    Used for managing a stream of data to and from a socket; input a socket
    """
    def __init__(self, s, remove_on_send=False):
        threading.Thread.__init__(self)
        self.daemon = True
        self.s = s
        # start of stream variables
        self.stream_dictionary = dict()
        self.frames_to_send = deque()
        self.frames_to_read = deque()
        # end of stream variables
        self.dictionary_lock = threading.Lock()
        self.should_run = threading.Event()
        self.timeout = 0.001
        self.remove_on_send = remove_on_send

    def run(self):
        performed = 0
        while not self.should_run.isSet():
            ready_to_read, ready_to_write, in_error = select_ceptic([self.s], [], [], self.timeout)
            # if ready to read, attempt to get frame from socket
            for sock in ready_to_read:
                # get frame
                try:
                    received_frame = StreamFrame().recv(sock)
                except EOFError:
                    continue
                # if id exists in dictionary, replace appropriate part of it
                if received_frame.id in self.stream_dictionary:
                    self.stream_dictionary[received_frame.id].replace(received_frame)
                else:
                    self.add_frame_to_dict(received_frame)
                # add frame into ready to read deque
                self.frames_to_read.append(received_frame.get_id())
            # if there is new frame(s) to send, attempt to send frame to socket
            if self.is_ready_to_send():
                #print("RUN frame is ready to send!")
                frame_to_send = self.get_ready_to_send()
                frame_to_send.send(self.s)
                if self.remove_on_send:
                    self.pop(frame_to_send.get_id())
            if performed%1000 == 0:
                print("RUN function performed {} times".format(performed))
            performed += 1

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
        frame_id = self.frames_to_send.popleft()
        return self.stream_dictionary[frame_id]

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
        :param frame_id: string uuid mapped to StreamFrame object in dictionary OR StreamFrame with corresponding uuid
        :return: StreamFrame object if exists, None if does not
        """
        if isinstance(frame_id,StreamFrame):
            frame_id = frame_id.id
        return self.stream_dictionary.pop(frame_id, None)

    def stop(self):
        self.should_run.set()

    def add(self, frame):
        self.add_frame_to_dict(frame)
        self.frames_to_send.append(frame.get_id())

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
    def __init__(self, count=None, data=None, buffer_size=1024000, s=None):
        self.buffering_size = buffer_size
        if s is not None:
            self.recv(s)
        else:
            self.id = str(uuid.uuid4())
            if count is None:
                self.count = 1
            else:
                self.count = int(count)
            if data is None:
                self.data = [""]*self.count
            else:
                self.data = data
            self.done = False

    def is_done(self):
        return self.done

    def set_done(self):
        self.done = True

    def unset_done(self):
        self.done = False

    def get_id(self):
        return self.id

    def get_data(self):
        return self.data

    def get_data(self, count):
        return self.data[count]

    def __str__(self):
        return self.id

    def replace(self, frame):
        # if data is not the same length, overwrite all data
        if len(self.data) != len(frame.data):
            self.count = frame.count
            self.data = frame.data
        # otherwise, replace only data that is not empty 
        else:
            for n in range(0,len(frame.data)):
                if frame.data[n]:
                    self.data[n] = frame.data[n]

    def recv(self, s):
        """
        Receives StreamFrame data via provided socket
        :param s: socket used to receive frame
        :return: object instance (self)
        """
        raw_frame_data_list = []
        raw_term_data_list = []
        # get StreamFrame UUID

        self.id = str(s.recv(36).strip())
        # get data count
        self.count = int(str(s.recv(16).strip()))
        # get size of each data
        data_size = []
        for size in range(0,self.count):
            data_size.append(int(str(s.recv(16).strip())))
        # get all data
        data = []
        for size in data_size:
            if size == 0:
                data.append(None)
            else:
                raw_data_list = []
                received = 0
                while received < size:
                    raw_data_part = s.recv(self.buffering_size)
                    # if no data, break out of receiving
                    if not raw_data_part:
                        break
                    else:
                        raw_data_list.append(raw_data_part)
                        received += len(raw_data_part)
                data.append(raw_data_list)
        # join data parts
        for n in range(0,len(data)):
            if data[n] is not None:
                data[n] = "".join(data[n])
        # set self.data to data
        self.data = data
        # return self
        return self

    def send(self, s):
        """
        Sends StreamFrame data via provided port
        :param s: socket used to send frame
        :return: None
        """
        # check if frame_data and term_data have been provided
        if self.count is None:
            raise StreamManagerException("No data in frame instance to send")
        
        # get sizes of data to be sent (16 byte blocks)
        #frame_data_size = '%16d' % len(self.frame_data)
        #term_data_size = '%16d' % len(self.term_data)
        # send id, count, data lengths (resp.) and data (resp.) in that order
        s.sendall(self.id)
        s.sendall('%16d' % self.count)
        for d in self.data:
            if not d:
                s.sendall('%16d' % 0)
                continue    
            s.sendall('%16d' % len(d))
        for d in self.data:
            if not d:
                continue
            s.sendall(d)
