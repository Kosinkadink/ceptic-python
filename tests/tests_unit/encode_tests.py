import pytest
from ceptic.encode import EncodeBase64, EncodeGZip, EncodeNone, EncodeGetter, UnknownEncodingException


def test_encode_and_decode_base64():
    # Arrange
    original = "someTestString123!@#".encode()
    # Act
    encoded = EncodeBase64.encode(original)
    decoded = EncodeBase64.decode(encoded)
    # Assert
    assert original == decoded
    assert original != encoded
    assert encoded != decoded


def test_encode_and_decode_gzip():
    # Arrange
    original = "someTestString123!@#".encode()
    # Act
    encoded = EncodeGZip.encode(original)
    decoded = EncodeGZip.decode(encoded)
    # Assert
    assert original == decoded
    assert original != encoded
    assert encoded != decoded


def test_encode_and_decode_none():
    # Arrange
    original = "someTestString123!@#".encode()
    # Act
    encoded = EncodeNone.encode(original)
    decoded = EncodeNone.decode(encoded)
    # Assert
    assert original == decoded
    assert original == encoded


def test_encode_getter_string_base64():
    # Arrange
    original = "someTestString123!@#".encode()
    encodings = EncodeBase64.name
    # Act
    handler = EncodeGetter.get(encodings)
    encoded = handler.encode(original)
    decoded = handler.decode(encoded)

    manual_encoded = EncodeBase64.encode(original)
    manual_decoded = EncodeBase64.decode(manual_encoded)
    # Assert
    assert original == decoded
    assert original != encoded
    assert encoded != decoded
    # make sure actually encodes properly
    assert encoded == manual_encoded
    assert decoded == manual_decoded


def test_encode_getter_string_gzip():
    # Arrange
    original = "someTestString123!@#".encode()
    encodings = EncodeGZip.name
    # Act
    handler = EncodeGetter.get(encodings)
    encoded = handler.encode(original)
    decoded = handler.decode(encoded)

    manual_encoded = EncodeGZip.encode(original)
    manual_decoded = EncodeGZip.decode(manual_encoded)
    # Assert
    assert original == decoded
    assert original != encoded
    assert encoded != decoded
    # make sure actually encodes properly
    assert encoded == manual_encoded
    assert decoded == manual_decoded


def test_encode_getter_string_none():
    # Arrange
    original = "someTestString123!@#".encode()
    encodings = EncodeNone.name
    # Act
    handler = EncodeGetter.get(encodings)
    encoded = handler.encode(original)
    decoded = handler.decode(encoded)

    manual_encoded = EncodeNone.encode(original)
    manual_decoded = EncodeNone.decode(manual_encoded)
    # Assert
    assert original == decoded
    assert original == encoded
    # make sure actually encodes properly
    assert encoded == manual_encoded
    assert decoded == manual_decoded


def test_encode_getter_string_base64_gzip():
    # Arrange
    original = "someTestString123!@#".encode()
    encodings = f'{EncodeBase64.name},{EncodeGZip.name}'
    # Act
    handler = EncodeGetter.get(encodings)
    encoded = handler.encode(original)
    decoded = handler.decode(encoded)

    manual_encoded = EncodeGZip.encode(EncodeBase64.encode(original))
    manual_decoded = EncodeBase64.decode(EncodeGZip.decode(manual_encoded))
    # Assert
    # Assert
    assert original == decoded
    assert original != encoded
    assert encoded != decoded
    # make sure actually encodes properly
    assert encoded == manual_encoded
    assert decoded == manual_decoded


def test_encode_getter_string_base64_none():
    # Arrange
    original = "someTestString123!@#".encode()
    encodings = f'{EncodeBase64.name},{EncodeNone.name}'
    # Act
    handler = EncodeGetter.get(encodings)
    encoded = handler.encode(original)
    decoded = handler.decode(encoded)
    # Assert
    # Assert
    assert len(handler.encoders) == 1
    assert handler.encoders[0] == EncodeNone
    assert original == decoded
    assert original == encoded


def test_encode_getter_invalid_encoding_unknown_encoding_exception():
    # Arrange, Act, Assert
    with pytest.raises(UnknownEncodingException):
        EncodeGetter.get("unknown")
