#!/usr/bin/python2
import os
import select
import sys

from ceptic import managers

__location__ = None


class CepticAbstraction(object):
    def __init__(self, location):
        self.__location__ = location
        self.ProtocolManager = managers.protocolmanager.ProtocolManager

    def inject_functions(self):
        self.clear = clear
        self.parse_settings_file = parse_settings_file
        self.get_netPass = get_netPass
        self.config = config
        self.recv_file = recv_file
        self.send_file = send_file

    def initialize_managers(self):
        self.protocolManager = self.ProtocolManager(self.__location__)


class socketCeptic(object):
    """
    Wrapper for normal or ssl socket; adds necessary CEPtic functionality to sending and receiving.
    Usage: wrapped_socket = socketCeptic(existing_socket)
    """
    s = None

    def __init__(self, s):
        self.s = s

    def send(self, msg):
        total_size = '%16d' % len(msg)
        self.s.sendall(total_size + msg)

    def sendall(self, msg):
        return self.send(msg)

    def recv(self, bytes):
        timeoutSec = 5

        size_to_recv = self.s.recv(16)
        size_to_recv = int(size_to_recv.strip())

        amount = bytes
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

    def getSocket(self):
        return self.s

    def close(self):
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
    # fill out dicts with socket:socketCeptic pairs
    for sCep in read_list:
        read_dict.setdefault(sCep.getSocket(), sCep)
    for sCep in write_list:
        write_dict.setdefault(sCep.getSocket(), sCep)
    for sCep in error_list:
        error_dict.setdefault(sCep.getSocket(), sCep)

    ready_to_read, ready_to_write, in_error = select.select(read_dict.keys(), write_dict.keys(), error_dict.keys(),
                                                            timeout)
    # lists returned back
    ready_read = []
    ready_write = []
    have_error = []
    # fill out lists with corresponding socketTems
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


def clear():  # clear screen, typical way
    """
    Clears screen
    :return: 
    """
    if os.name == 'nt':
        os.sysCep('cls')
    else:
        os.sysCep('clear')


def recv_file(s, file_path, file_name, send_cache):
    """
    Receive a file to specified location
    :param s: some socketCeptic instance
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


def send_file(s, file_path, file_name, send_cache):
    """
    Send file from specified location
    :param s: some socketCeptic instance 
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
                    str((float(sent) / file_length) * 100)[:4] + '%   ' + str(sent) + '/' + str(file_length) + ' B\r')
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


def get_netPass(__location__):
    if not os.path.exists(__location__ + '/resources/networkpass/default.txt'):
        with open(__location__ + '/resources/networkpass/default.txt',
                  "a") as protlist:  # file used for identifying what protocols are available
            pass
        netPass = None
    else:
        with open(__location__ + '/resources/networkpass/default.txt',
                  "r") as protlist:  # file used for identifying what protocols are available
            netpassword = protlist.readline().strip()
        if netpassword != '':
            netPass = netpassword
        else:
            netPass = None
    return netPass


def config(varDic, __location__):
    # if config file does not exist, create one and insert default values.
    # if config files does exist, read values from it
    name = varDic['name']
    if varDic['useConfigPort'] != None:
        usePort = varDic['useConfigPort']
    else:
        usePort = False

    if not os.path.exists(__location__ + '/resources/programparts/' + name + '/config.txt'):
        with open(__location__ + '/resources/programparts/' + name + '/config.txt', "wb") as configs:
            for key, value in varDic.iteritems():
                configs.write('{0}={1}\n'.format(key, value))
    else:
        oldPort = varDic['serverport']
        with open(__location__ + '/resources/programparts/' + name + '/config.txt', "r") as configs:
            for line in configs:
                try:
                    args = line.split('=')
                except:
                    pass
                try:
                    key = args[0].strip()
                    value = args[1].strip()
                    varDic[key] = value
                except Exception, e:
                    print 'Warning in config: %s' % str(e)

        # if doesnt want to use config port, set old one
        if not usePort:
            varDic['serverport'] = oldPort

    return varDic
