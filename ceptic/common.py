import os
import sys
from sys import version_info


def create_command_settings(maxMsgLength=2048000000,maxBodyLength=2048000000):
    """
    Generates dictionary with command settings
    """
    settings = {}
    settings["maxMsgLength"] = int(maxMsgLength)
    settings["maxBodyLength"] = int(maxBodyLength)
    return settings


class CepticCommands(object):
    GET = "get"
    POST = "post"
    UPDATE = "update"
    DELETE = "delete"
    STREAM = "stream"
    STREAMGET = "streamget"
    STREAMPOST = "streampost"


class CepticStatusCode(object):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500

    @staticmethod
    def is_success(status_code):
        return status_code >= 200 and status_code <= 299
    @staticmethod
    def is_error(status_code):
        return status_code >= 400 and status_code <= 599
    @staticmethod
    def is_client_error(status_code):
        return status_code >= 400 and status_code <= 499
    @staticmethod
    def is_server_error(status_code):
        return status_code >= 500 and status_code <= 599


class CepticResponse(object):
    def __init__(self, status, msg, stream=None):
        self.status = int(status)
        self.msg = msg
        self.stream = stream
    def get_dict(self):
        return {"status":self.status, "msg":self.msg}
    @staticmethod
    def get_with_socket(s, max_msg_length):
        status = int(s.recv(3))
        msg = s.recv(max_msg_length)
        return CepticResponse(status,msg)
    def send_with_socket(self, s):
        s.sendall('%3d' % self.status)
        s.sendall(self.msg)
    def __repr__(self):
        return str(self.get_dict())
    def __str__(self):
        return self.__repr__()


class CepticRequest(object):
    def __init__(self, command=None,endpoint=None,headers=None,body=None,settings=None):
        self.command = command
        self.endpoint = endpoint
        self.headers = headers
        self.body = body
        self.settings = settings


class CepticException(Exception):
    """
    General Ceptic-related exception class
    """
    pass


class FileFrame(object):
    """
    Object to store metadata about a file to be sent/received
    """
    def __init__(self, file_name, file_path, send_cache):
        self.file_name = file_name
        self.file_path = file_path
        self.send_cache = send_cache
        if version_info >= (3,0): # check if running python3
            self.recv = self.recv_py3

    def send(self, s):
        """
        Send file from specified location
        :param s: some SocketCeptic instance 
        :param file_path: full path of file location
        :param file_name: filename of file; for display purposes only
        :param send_cache: amount of bytes to attempt to send at a time
        :return: status of upload (success: 200, failure: 400)
        """
        file_name = self.file_name
        file_path = self.file_path
        send_cache = self.send_cache
        try:
            # check if file exists, and if not send file length as all "n"
            if not os.path.isfile(file_path):
                s.sendall("n"*16)
                raise IOError("No file found at {}".format(file_path))
            file_length = os.path.getsize(file_path)
            # send size of file
            s.sendall("%16d" % file_length)
            # open file and send it
            print(file_path)
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
        except Exception as e:
            print("ERROR has occured while sending file")
            return {"status": 400, "msg": "{}".format(str(e))}

    def recv(self, s):
        """
        Receive a file to specified location
        :param s: some SocketCeptic instance
        :param file_path: full path of save location
        :param file_name: filename of file; for display purposes only
        :param send_cache: amount of bytes to attempt to receive at a time
        :return: status of download (success: 200, failure: 400)
        """
        file_name = self.file_name
        file_path = self.file_path
        send_cache = self.send_cache
        try:
            # get size of file
            received_string = s.recv(16).strip()
            if received_string == "n"*16:
                raise IOError("No file found ({}) on sender side".format(file_name))
            file_length = int(received_string)
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
        except Exception as e:
            print("ERROR has occured while receiving file")
            return {"status": 400, "msg": "{}".format(str(e))}

    def recv_py3(self, s):
        """
        Receive a file to specified location
        :param s: some SocketCeptic instance
        :param file_path: full path of save location
        :param file_name: filename of file; for display purposes only
        :param send_cache: amount of bytes to attempt to receive at a time
        :return: status of download (success: 200, failure: 400)
        """
        file_name = self.file_name
        file_path = self.file_path
        send_cache = self.send_cache
        try:
            # get size of file
            received_string = s.recv(16).strip()
            if received_string == "n"*16:
                raise IOError("No file found ({}) on sender side".format(file_name))
            file_length = int(received_string)
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
                    data = s.recv(send_cache).encode()
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
        except Exception as e:
            print("ERROR has occured while receiving file")
            return {"status": 400, "msg": "{}".format(str(e))}


def normalize_path(path):
    """
    Changes paths to contain only forward slashes; Windows inter-compatibility fix
    :param path: string path
    :return: forward slash-only path
    """
    if os.name == 'nt':
        path = path.replace('\\', '/')
    return path


def decode_unicode_hook(json_pairs):
    """
    Given json pairs, properly encode strings into utf-8 for general usage
    :param json_pairs: dictionary of json key-value pairs
    :return: new dictionary of json key-value pairs in utf-8
    """
    if version_info >= (3,0): # is 3.X
        return dict(json_pairs)
    new_json_pairs = []
    for key, value in json_pairs:
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        if isinstance(key, unicode):
            key = key.encode("utf-8")
        new_json_pairs.append((key, value))
    return dict(new_json_pairs)
