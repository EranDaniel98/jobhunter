"""Magic-byte validation for uploaded files.

Content-Type headers are trivially spoofable. These helpers check the actual
file bytes against known format signatures so a malicious upload claiming
Content-Type: image/png can't actually be an executable or HTML payload.
"""

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_RIFF = b"RIFF"
_WEBP = b"WEBP"


def is_valid_image_bytes(data: bytes) -> bool:
    """Return True if the bytes match a PNG/JPEG/GIF/WebP signature.

    Validates the first 12 bytes; no format parsing beyond the header —
    this is a spoofing guard, not a format-integrity check.
    """
    if len(data) < 12:
        return False
    if data.startswith(_PNG):
        return True
    if data.startswith(_JPEG):
        return True
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return True
    # WebP: "RIFF" + 4 bytes size + "WEBP"
    return data.startswith(_RIFF) and data[8:12] == _WEBP
