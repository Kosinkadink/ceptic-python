import base64
import io

from abc import ABC
from ceptic.common import CepticException
from gzip import GzipFile

from typing import List, Type


class EncoderException(CepticException):
    """
    Exception related to the EncodeGetter class.
    """
    pass


class UnknownEncodingException(EncoderException):
    """
    Unknown Compression Exception, inherits from EncoderException.
    """
    pass


class EncodeObject(ABC):
    """
    Object for compression abstraction purposes
    """

    @staticmethod
    def encode(data: bytes) -> bytes:
        return data

    @staticmethod
    def decode(data: bytes) -> bytes:
        return data


class EncodeNone(EncodeObject):
    """
    Encoder that does not modify data.
    """
    name = "none"

    @staticmethod
    def encode(data: bytes) -> bytes:
        return data

    @staticmethod
    def decode(data: bytes) -> bytes:
        return data


class EncodeGZip(EncodeObject):
    """
    Encodes and decodes to and from gzip encoding. GZip is a form of compression.
    """
    name = "gzip"

    @staticmethod
    def encode(data: bytes) -> bytes:
        out_data = io.BytesIO()
        with GzipFile(fileobj=out_data, mode="wb") as mem_file:
            mem_file.write(data)
        return out_data.getvalue()

    @staticmethod
    def decode(data: bytes) -> bytes:
        in_data = io.BytesIO(data)
        with GzipFile(fileobj=in_data, mode="rb") as mem_file:
            return mem_file.read()


class EncodeBase64(EncodeObject):
    """
    Encodes and decodes to and from base64 encoding.
    """
    name = "base64"

    @staticmethod
    def encode(data: bytes) -> bytes:
        return base64.b64encode(data)

    @staticmethod
    def decode(data: bytes) -> bytes:
        return base64.b64decode(data)


class EncodeHandler(object):
    """
    Encodes and decodes using a series of one or more encoders.
    """
    def __init__(self, encoders: list[Type[EncodeObject]]) -> None:
        self.encoders = encoders

    def encode(self, data: bytes) -> bytes:
        for encoder in self.encoders:
            data = encoder.encode(data)
        return data

    def decode(self, data: bytes) -> bytes:
        for encoder in reversed(self.encoders):
            data = encoder.decode(data)
        return data


class EncodeGetter(object):
    """
    Returns EncodeObject based on corresponding string.
    """
    encode_dict = {
        EncodeNone.name: EncodeNone,
        EncodeGZip.name: EncodeGZip,
        EncodeBase64.name: EncodeBase64
    }

    @staticmethod
    def get(encodings: str) -> EncodeHandler:
        if not encodings:
            return EncodeHandler([EncodeNone])
        encodings_list = encodings.strip().split(",")
        # find encoders and add them to list; only add unique encoders
        unique_names = set()
        encoders = []
        for name in encodings_list:
            # if EncodeNone included, don't do any other encoding
            if name == EncodeNone.name:
                return EncodeHandler([EncodeNone])
            # try to get encode class
            encode_class = EncodeGetter.encode_dict.get(name)
            if not encode_class:
                raise UnknownEncodingException("Encode type is not recognized: {}.".format(name))
            # add to list if unique
            if name not in unique_names:
                encoders.append(encode_class)
                unique_names.add(name)
        # create and return EncodeHandler
        return EncodeHandler(encoders)
