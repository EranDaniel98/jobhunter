"""Magic-byte validation helpers (#104)."""
from app.utils.file_validation import is_valid_image_bytes


class TestIsValidImageBytes:
    def test_accepts_png(self):
        assert is_valid_image_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    def test_accepts_jpeg(self):
        assert is_valid_image_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)

    def test_accepts_gif87(self):
        assert is_valid_image_bytes(b"GIF87a" + b"\x00" * 16)

    def test_accepts_gif89(self):
        assert is_valid_image_bytes(b"GIF89a" + b"\x00" * 16)

    def test_accepts_webp(self):
        # RIFF + 4-byte size + WEBP
        assert is_valid_image_bytes(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16)

    def test_rejects_empty(self):
        assert not is_valid_image_bytes(b"")

    def test_rejects_short(self):
        assert not is_valid_image_bytes(b"\x89PNG")  # <12 bytes

    def test_rejects_executable(self):
        # PE/COFF Windows executable header
        assert not is_valid_image_bytes(b"MZ\x90\x00" + b"\x00" * 16)

    def test_rejects_elf(self):
        assert not is_valid_image_bytes(b"\x7fELF" + b"\x00" * 16)

    def test_rejects_html(self):
        assert not is_valid_image_bytes(b"<!DOCTYPE html>" + b"\x00" * 16)

    def test_rejects_spoofed_text(self):
        # Attacker: claims Content-Type: image/png, sends arbitrary text
        assert not is_valid_image_bytes(b"fake image content here" + b"\x00" * 16)

    def test_rejects_riff_without_webp_marker(self):
        # RIFF container but not WebP (e.g., AVI, WAV)
        assert not is_valid_image_bytes(b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 16)
