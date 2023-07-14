from ceptic.common import CepticException
from select import select as vanilla_select
from socket import socket

from typing import Union, Iterable, Tuple, List


class SocketCepticException(CepticException):
    """
    General SocketCeptic Exception, inherits from CepticException
    """
    pass


class SocketCeptic(object):
    """
    Wrapper for normal or ssl socket; adds necessary CEPtic functionality to sending and receiving.
    Usage: wrapped_socket = SocketCeptic(existing_socket)
    """
    
    def __init__(self, s: socket) -> None:
        self.s = s

    # region Send
    def send_raw(self, msg: bytes) -> None:
        """
        Send message without prefix.
        :param msg: bytes to send
        :raises SocketCepticException: when socket is unexpectedly closed.
        """
        sent = 0
        while sent < len(msg):
            try:
                sent += self.s.send(msg[sent:])
            except ConnectionResetError as e:
                raise SocketCepticException("Connection was closed: {}".format(str(e))) from e

    def send_raw_str(self, msg: str) -> None:
        """
        Send message without prefix.
        :param msg: string to send
        :raises SocketCepticException: when socket is unexpectedly closed.
        """
        return self.send_raw(msg.encode())

    def send(self, msg: bytes) -> None:
        """
        Send message, prefixed by a 16-byte length.
        :param msg: bytes to send
        :raises SocketCepticException: when socket is unexpectedly closed.
        """
        total_size = format(len(msg), ">16").encode()
        self.send_raw(total_size)
        self.send_raw(msg)

    def send_str(self, msg: str) -> None:
        """
        Send message, prefixed by a 16-byte length.
        :param msg: str to send
        :raises SocketCepticException: when socket is unexpectedly closed.
        """
        self.send(msg.encode())
    # endregion

    # region Receive
    def recv_raw(self, length: int) -> bytes:
        """
        Receive bytes up to the length specified.
        :param length: length of byte array to receive
        :raises SocketCepticException: when socket is unexpectedly closed or EOF
        """
        recv_amount = 0
        byte_array = bytearray()
        try:
            while recv_amount < length:
                part = self.s.recv(length - recv_amount)
                recv_amount += len(part)
                byte_array += part
                if not part:
                    break
        except ConnectionResetError as e:
            raise SocketCepticException("Connection was closed: {}".format(str(e))) from e
        except (EOFError, OSError) as e:
            raise SocketCepticException("No data received (EOF).") from e
        return byte_array

    def recv_raw_str(self, length: int) -> str:
        """
        Receive string up to the length specified.
        :param length: length of string to receive
        :raises SocketCepticException: when socket is unexpectedly closed or EOF
        """
        return self.recv_raw(length).decode()

    def recv_bytes(self, max_length: int) -> bytes:
        """
        Receive bytes up to the maximum length specified, with a sender-provided prefix for the exact length of message.
        :param max_length: maximum length of byte array expected from sender
        :raises SocketCepticException: when socket is unexpectedly closed or EOF
        """
        try:
            size_to_recv = int(self.recv_raw_str(16).strip())
        except ValueError as e:
            raise SocketCepticException("no data received (EOF) from size prefix.") from e
        if size_to_recv < max_length:
            max_length = size_to_recv
        return self.recv_raw(max_length)

    def recv_str(self, max_length: int) -> str:
        """
        Receive bytes up to the maximum length specified, with a sender-provided prefix for the exact length of message.
        :param max_length: maximum length of byte array expected from sender
        :raises SocketCepticException: when socket is unexpectedly closed or EOF
        """
        return self.recv_bytes(max_length).decode()
    # endregion

    def close(self) -> None:
        """
        Close wrapped socket.
        """
        self.s.close()


def select(read_list: Iterable[SocketCeptic], write_list: Iterable[SocketCeptic], error_list: Iterable[SocketCeptic],
           timeout: Union[float, None]) -> Tuple[list[SocketCeptic], list[SocketCeptic], list[SocketCeptic]]:
    """
    Wraps select.select for use with SocketCeptic instances. See select.select documentation for full expected behavior.
    :param read_list: wait until ready for reading
    :param write_list: wait until ready for writing
    :param error_list: wait for an "exceptional condition"
    :param timeout: optional timeout in seconds to wait for results
    """
    read_dict = {}
    write_dict = {}
    error_dict = {}
    # fill out dicts with socket:SocketCeptic pairs
    for cep in read_list:
        read_dict.setdefault(cep.s, cep)
    for cep in write_list:
        write_dict.setdefault(cep.s, cep)
    for cep in error_list:
        error_dict.setdefault(cep.s, cep)

    r, w, e = vanilla_select(read_dict.keys(), write_dict.keys(), error_dict.keys(), timeout)

    # lists to return
    ready_to_read = [read_dict[sock] for sock in r]
    ready_to_write = [write_dict[sock] for sock in w]
    have_error = [error_dict[sock] for sock in e]

    return ready_to_read, ready_to_write, have_error
