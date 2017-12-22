#!/usr/bin/python2

import os
import select
import sys
from sys import version_info

# NOTE: "import ceptic.managers as managers" is found on bottom of file to work around circular import


class CepticAbstraction(object):
    """
    Object used to store common elements between CepticClient and CepticServer
    """

    def __init__(self, location):
        self.__location__ = location
        self.fileManager = managers.filemanager.FileManager(self.__location__)
        self.protocolManager = managers.protocolmanager.ProtocolManager(self.__location__)
        self.terminalManager = managers.terminalmanager.TerminalManager()
        self.endpointManager = managers.endpointmanager.EndpointManager()

    def add_terminal_commands(self):
        """
        Add additional terminal commands here by overriding this function
        :return: None
        """
        pass

    def add_endpoint_commands(self):
        """
        Add additional endpoints here bu overriding this function
        :return: None
        """
        pass

    def service_terminal(self, inp):  # used for server commands
        """
        Pass input into terminalManager
        :param inp: raw string input
        :return: return value of whatever terminal command, or None
        """
        try:
            # get command from terminal manager and run it with input
            return self.terminalManager.perform_input(inp)
        except TerminalManagerException as e:
            print(str(e))
        except Exception as e:
            print(str(e))

    def recv_file(self, s, file_path, file_name, send_cache):
        """
        Receive a file to specified location
        :param s: some SocketCeptic instance
        :param file_path: full path of save location
        :param file_name: filename of file; for display purposes only
        :param send_cache: amount of bytes to attempt to receive at a time
        :return: status of download (success: 200, failure: 400)
        """
        # get size of file
        file_length = int(s.recv(16).strip())

        with open(file_path, 'wb') as f:
            print("{} receiving...".format(file_name))
            received = 0
            while file_length > received:
                # print progress of download, ignore if cannot display
                try:
                    sys.stdout.write(
                        str((float(received) / file_length) * 100)[:4] + '%   ' + str(received) + '/' + str(file_length)
                        + 'B\r'
                    )
                    sys.stdout.flush()
                except:
                    pass
                data = s.recv(send_cache)
                if not data:
                    break
                received += len(data)
                f.write(data)
        # send heartbeat
        s.sendall("ok")
        sys.stdout.write('100.0%   ' + str(received) + '/' + str(file_length) + ' B\n')
        print("{} receiving successful".format(file_name))
        # return metadata
        return {"status": 200, "msg": "OK"}

    def send_file(self, s, file_path, file_name, send_cache):
        """
        Send file from specified location
        :param s: some SocketCeptic instance 
        :param file_path: full path of file location
        :param file_name: filename of file; for display purposes only
        :param send_cache: amount of bytes to attempt to send at a time
        :return: status of upload (success: 200, failure: 400)
        """
        # get size of file to be sent
        file_length = os.path.getsize(file_path)
        # send size of file
        s.sendall("%16d" % file_length)
        # open file and send it
        with open(file_path, 'rb') as f:
            print("{} sending...".format(file_name))
            sent = 0
            while file_length > sent:
                # print progress of upload, ignore if cannot display
                try:
                    sys.stdout.write(
                        str((float(sent) / file_length) * 100)[:4] + '%   ' + str(sent) + '/' + str(
                            file_length) + ' B\r')
                    sys.stdout.flush()
                except:
                    pass
                data = f.read(send_cache)
                s.sendall(data)
                if not data:
                    break
                sent += len(data)
        # get heartbeat
        s.recv(2)
        sys.stdout.write('100.0%   ' + str(sent) + '/' + str(file_length) + ' B\n')
        print("{} sending successful".format(file_name))
        # return metadata
        return {"status": 200, "msg": "OK"}

    def clear(self):
        """
        Clears screen
        :return: None
        """
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')


class CepticException(Exception):
    """
    General Ceptic-related exception class
    """
    pass


class SocketCeptic(object):
    """
    Wrapper for normal or ssl socket; adds necessary CEPtic functionality to sending and receiving.
    Usage: wrapped_socket = SocketCeptic(existing_socket)
    """
    def __init__(self, s):
        self.s = s

    def send(self, msg):
        """
        Send message, prefixed by a 16-byte length
        :param msg: string or bytes to send
        :return: None
        """
        total_size = '%16d' % len(msg)
        self.s.sendall(total_size + msg)

    def sendall(self, msg):
        """
        Send message, wrapper for SocketCeptic.send
        :param msg: string or bytes to send
        :return: None
        """
        return self.send(msg)

    def recv(self, byte_amount):
        """
        Receive message, first the 16-byte length prefix, then the message of corresponding length. No more than the
        specified amount of bytes will be received, but based on the received length less bytes could be received
        :param byte_amount: integer
        :return: received bytes, readable as a string
        """
        size_to_recv = self.s.recv(16)
        size_to_recv = int(size_to_recv.strip())

        amount = byte_amount
        if size_to_recv < amount:
            amount = size_to_recv
        recvd = 0
        text = ""
        while recvd < amount:
            part = self.s.recv(amount)
            recvd += len(part)
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


def normalize_path(path):
    """
    Changes paths to contain only forward slashes; Windows inter-compatibility fix
    :param path: string path
    :return: forward slash-only path
    """
    if os.name == 'nt':
        path = path.replace('\\', '/')
    return path


def parse_settings_file(location):
    """
    Parse a settings file into list; all lines not starting with # are parsed, values separated by |
    :param location: settings file path
    :return: list containing parsed values
    """
    parsed = []
    with open(location, "rb") as settings:
        for line in settings:
            if not line.startswith("#"):
                parsed.append(line.strip().split('|'))
    return parsed


def decode_unicode_hook(json_pairs):
    """
    Given json pairs, properly encode strings into utf-8 for general usage
    :param json_pairs: dictionary of json key-value pairs
    :return: new dictionary of json key-value pairs in utf-8
    """
    new_json_pairs = []
    for key, value in json_pairs:
        if version_info < (3,0): # is 2.X
            if isinstance(value, unicode):
                value = value.encode("utf-8")
            if isinstance(key, unicode):
                key = key.encode("utf-8")
        new_json_pairs.append((key, value))
    return dict(new_json_pairs)


import ceptic.managers as managers
from ceptic.managers.terminalmanager import TerminalManagerException
