import gzip
from sys import version_info
if version_info < (3, 0):  # if running python 2
    import StringIO
else:
    import io
from ceptic.common import CepticException


class CompressorException(CepticException):
    """
    Exception related to the CompressGetter class
    """
    pass


class UnknownCompressionException(CompressorException):
    """
    Unknown Compression Exception, inherits from CompressorException
    """


class CompressObject(object):
    """
    Object for compression abstraction purposes
    """

    @staticmethod
    def compress(data):
        return data

    @staticmethod
    def decompress(data):
        return data


class CompressNone(CompressObject):
    name = "None"

    @staticmethod
    def compress(data):
        return data

    @staticmethod
    def decompress(data):
        return data


class CompressGzip(CompressObject):
    name = "gzip"

    @staticmethod
    def compress(data):
        if version_info < (3, 0):
            return CompressGzip.__compress_py2(data)
        else:
            return CompressGzip.__compress_py3(data)

    @staticmethod
    def decompress(data):
        if version_info < (3, 0):
            return CompressGzip.__decompress_py2(data)
        else:
            return CompressGzip.__decompress_py3(data)

    @staticmethod
    def __compress_py2(data):
        out_data = StringIO.StringIO()
        with gzip.GzipFile(fileobj=out_data, mode="wb") as mem_file:
            mem_file.write(data)
        return out_data.getvalue()

    @staticmethod
    def __decompress_py2(data):
        in_data = StringIO.StringIO(data)
        with gzip.GzipFile(fileobj=in_data, mode="rb") as mem_file:
            decompressed = mem_file.read()
        return decompressed

    @staticmethod
    def __compress_py3(data):
        out_data = io.BytesIO()
        with gzip.GzipFile(fileobj=out_data, mode="wb") as mem_file:
            try:
                mem_file.write(data.encode())
            except AttributeError:
                mem_file.write(data)
        return out_data.getvalue()

    @staticmethod
    def __decompress_py3(data):
        in_data = io.BytesIO(data)
        with gzip.GzipFile(fileobj=in_data, mode="rb") as mem_file:
            decompressed = mem_file.read()
        return decompressed


class CompressGetter(object):
    """
    Returns CompressObject based on corresponding string
    """
    compress_dict = {
        CompressNone.name: CompressNone,
        CompressGzip.name: CompressGzip
    }

    @staticmethod
    def get(name):
        """
        Returns corresponding CompressObject; throws UnknownCompressionException if not found
        :param name: string name of compression method
        :return:
        """
        if not name:
            name = "None"
        compress_class = CompressGetter.compress_dict.get(name)
        if not compress_class:
            raise UnknownCompressionException("compress type is not recognized: {}".format(name))
        return compress_class
