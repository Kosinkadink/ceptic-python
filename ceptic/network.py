import select
from sys import version_info


class SocketCeptic(object):
    def __init__(self, s):
        pass

    def __new__(cls, s):
        if version_info < (3, 0):  # python2 code
            actual_class = SocketCepticPy2
        else:
            actual_class = SocketCepticPy3
        instance = super(SocketCeptic, actual_class).__new__(actual_class)
        if actual_class != cls:
            instance.__init__(s)
        return instance

    def send(self, msg):
        pass

    def sendall(self, msg):
        pass

    def send_raw(self, msg):
        pass

    def recv(self, byte_amount):
        pass

    def recv_raw(self, byte_amount):
        pass

    def get_socket(self):
        pass

    def close(self):
        pass


class SocketCepticPy2(SocketCeptic):
    """
    Wrapper for normal or ssl socket; adds necessary CEPtic functionality to sending and receiving.
    Usage: wrapped_socket = SocketCeptic(existing_socket)
    """

    def __init__(self, s):
        super(SocketCepticPy2, self).__init__(s)
        self.s = s

    def send(self, msg):
        """
        Send message, prefixed by a 16-byte length
        :param msg: string or bytes to send
        :return: None
        """
        # if there is nothing to send, then don't just send size
        if not msg:
            return
        total_size = format(len(msg), ">16")
        self.send_raw(total_size)
        self.send_raw(msg)

    def sendall(self, msg):
        """
        Send message, wrapper for SocketCeptic.send
        :param msg: string or bytes to send
        :return: None
        """
        return self.send(msg)

    def send_raw(self, msg):
        """
        Send message without prefix
        :param msg: string or bytes to send
        :return: None
        """
        # if there is nothing to send, then do nothing
        if not msg:
            return
        sent = 0
        while sent < len(msg):
            sent += self.s.send(msg[sent:])

    def recv(self, byte_amount):
        """
        Receive message, first the 16-byte length prefix, then the message of corresponding length. No more than the
        specified amount of bytes will be received, but based on the received length less bytes could be received
        :param byte_amount: integer
        :return: received bytes, readable as a string
        """
        try:
            size_to_recv = self.recv_raw(16)
            size_to_recv = int(size_to_recv.strip())
        except ValueError:
            raise EOFError("no data received (EOF)")
        except OSError:
            raise EOFError("no data received (EOF)")
        amount = byte_amount
        if size_to_recv < amount:
            amount = size_to_recv
        return self.recv_raw(amount)

    def recv_raw(self, byte_amount):
        recv_amount = 0
        text = ""
        while recv_amount < byte_amount:
            part = self.s.recv(byte_amount-recv_amount)
            recv_amount += len(part)
            text += part
            if part == "":
                break
        return text

    def get_socket(self):
        """
        Return raw socket instance
        :return: basic socket instance (socket.socket)
        """
        return self.s

    def close(self):
        """
        Close socket
        :return: None
        """
        self.s.close()


class SocketCepticPy3(SocketCeptic):
    """
    Wrapper for normal or ssl socket; adds necessary CEPtic functionality to sending and receiving.
    Usage: wrapped_socket = SocketCeptic(existing_socket)
    """

    def __init__(self, s):
        super().__init__(s)
        self.s = s

    def send(self, msg):
        """
        Send message, prefixed by a 16-byte length
        :param msg: string or bytes to send
        :return: None
        """
        # if there is nothing to send, then don't just send size
        if not msg:
            return
        total_size = format(len(msg), ">16")
        # send length and msg
        self.send_raw(total_size)
        self.send_raw(msg)

    def sendall(self, msg):
        """
        Send message, wrapper for SocketCeptic.send
        :param msg: string or bytes to send
        :return: None
        """
        return self.send(msg)

    def send_raw(self, msg):
        """
        Send message without prefix
        :param msg: string or bytes to send
        :return: None
        """
        # if there is nothing to send, then don't just send size
        if not msg:
            return
        # if it is already in bytes, do not encode it
        sent = 0
        while sent < len(msg):
            try:
                sent += self.s.send(msg[sent:].encode())
            except AttributeError:
                sent += self.s.send(msg[sent:])

    def recv(self, byte_amount):
        """
        Receive message, first the 16-byte length prefix, then the message of corresponding length. No more than the
        specified amount of bytes will be received, but based on the received length less bytes could be received
        :param byte_amount: integer
        :return: received bytes, readable as a string
        """
        try:
            size_to_recv = self.recv_raw(16)
            size_to_recv = int(size_to_recv.strip())
        except ValueError:
            raise EOFError("no data received (EOF)")
        except OSError:
            raise EOFError("no data received (EOF)")
        amount = byte_amount
        if size_to_recv < byte_amount:
            amount = size_to_recv
        return self.recv_raw(amount)

    def recv_raw(self, byte_amount):
        """
        Receive message of corresponding length. No more than the
        specified amount of bytes will be received
        :param byte_amount: integer
        :return: received bytes, readable as a string
        """
        recv_amount = 0
        text = bytes()
        while recv_amount < byte_amount:
            part = self.s.recv(byte_amount-recv_amount)
            recv_amount += len(part)
            text += part
            if part == "":
                break
        return text.decode()

    def get_socket(self):
        """
        Return raw socket instance
        :return: basic socket instance (socket.socket)
        """
        return self.s

    def close(self):
        """
        Close socket
        :return: None
        """
        self.s.close()


def select_ceptic(read_list, write_list, error_list, timeout):
    """
    CEPtic wrapper version of the select function
    :param read_list: see select.select
    :param write_list: see select.select
    :param error_list: see select.select
    :param timeout: see select.select
    :return: see select.select
    """
    read_dict = {}
    write_dict = {}
    error_dict = {}
    # fill out dicts with socket:SocketCeptic pairs
    for sCep in read_list:
        read_dict.setdefault(sCep.get_socket(), sCep)
    for sCep in write_list:
        write_dict.setdefault(sCep.get_socket(), sCep)
    for sCep in error_list:
        error_dict.setdefault(sCep.get_socket(), sCep)

    ready_to_read, ready_to_write, in_error = select.select(read_dict.keys(), write_dict.keys(), error_dict.keys(),
                                                            timeout)
    # lists returned back
    ready_read = []
    ready_write = []
    have_error = []
    # fill out lists with corresponding SocketCeptics
    for sock in ready_to_read:
        ready_read.append(read_dict[sock])
    for sock in ready_to_write:
        ready_write.append(write_dict[sock])
    for sock in in_error:
        have_error.append(error_dict[sock])

    return ready_read, ready_write, have_error
