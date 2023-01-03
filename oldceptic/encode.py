import gzip
import base64
from sys import version_info
if version_info < (3, 0):  # if running python 2
    import StringIO
else:
    import io
from oldceptic.common import CepticException


class EncoderException(CepticException):
    """
    Exception related to the EncodeGetter class
    """
    pass


class UnknownEncodingException(EncoderException):
    """
    Unknown Compression Exception, inherits from EncoderException
    """


class EncodeObject(object):
    """
    Object for compression abstraction purposes
    """

    @staticmethod
    def encode(data):
        return data

    @staticmethod
    def decode(data):
        return data


class EncodeNone(EncodeObject):
    name = "None"

    @staticmethod
    def encode(data):
        return data

    @staticmethod
    def decode(data):
        return data


class EncodeGzip(EncodeObject):
    name = "gzip"

    @staticmethod
    def encode(data):
        if version_info < (3, 0):
            return EncodeGzip.__encode_py2(data)
        else:
            return EncodeGzip.__encode_py3(data)

    @staticmethod
    def decode(data):
        if version_info < (3, 0):
            return EncodeGzip.__decode_py2(data)
        else:
            return EncodeGzip.__decode_py3(data)

    @staticmethod
    def __encode_py2(data):
        out_data = StringIO.StringIO()
        with gzip.GzipFile(fileobj=out_data, mode="wb") as mem_file:
            mem_file.write(data)
        return out_data.getvalue()

    @staticmethod
    def __decode_py2(data):
        in_data = StringIO.StringIO(data)
        with gzip.GzipFile(fileobj=in_data, mode="rb") as mem_file:
            decompressed = mem_file.read()
        return decompressed

    @staticmethod
    def __encode_py3(data):
        out_data = io.BytesIO()
        with gzip.GzipFile(fileobj=out_data, mode="wb") as mem_file:
            try:
                mem_file.write(data.encode())
            except AttributeError:
                mem_file.write(data)
        return out_data.getvalue()

    @staticmethod
    def __decode_py3(data):
        in_data = io.BytesIO(data)
        with gzip.GzipFile(fileobj=in_data, mode="rb") as mem_file:
            decompressed = mem_file.read()
        return decompressed


class EncodeBase64(EncodeObject):
    name = "base64"

    @staticmethod
    def encode(data):
        return base64.b64encode(data)

    @staticmethod
    def decode(data):
        return base64.b64decode(data)


class EncodeHandler(object):
    def __init__(self, encoder_list):
        self.encoders = encoder_list

    def encode(self, data):
        for encoder in self.encoders:
            data = encoder.encode(data)
        return data

    def decode(self, data):
        for encoder in reversed(self.encoders):
            data = encoder.decode(data)
        return data


class EncodeGetter(object):
    """
    Returns EncodeObject based on corresponding string
    """
    encode_dict = {
        EncodeNone.name: EncodeNone,
        EncodeGzip.name: EncodeGzip,
        EncodeBase64.name: EncodeBase64
    }

    @staticmethod
    def get(encodings):
        """
        Returns corresponding EncodeObject; throws UnknownEncodingException if not found
        :param encodings: comma-separated string names of encoding method(s)
        :return:
        """
        # if encodings is None, use EncodeNone
        if not encodings:
            return EncodeHandler([EncodeNone])
        unique_names = set()
        encoder_list = []
        # get encodings from encoding_names string
        encoding_names = encodings.split(",")
        # find encoders and add them to list; only add unique encoders
        for name in encoding_names:
            # if EncodeNone included, don't do any other encoding
            if name == EncodeNone.name:
                return EncodeHandler([EncodeNone])
            # try to get encode class
            encode_class = EncodeGetter.encode_dict.get(name)
            if not encode_class:
                raise UnknownEncodingException("encode type is not recognized: {}".format(name))
            # add to list if unique
            if name not in unique_names:
                encoder_list.append(encode_class)
        # create and return EncodeHandler
        return EncodeHandler(encoder_list)

    @staticmethod
    def check(encodings):
        try:
            EncodeGetter.get(encodings)
            return True, None
        except UnknownEncodingException as e:
            return False, str(e)
