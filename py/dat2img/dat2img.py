import os
import io
import struct
from typing import Tuple, Optional

try:
    from Crypto.Cipher import AES
except ImportError as e:
    raise RuntimeError("pycryptodome is required. Please install with: pip install pycryptodome") from e

# Format definitions
class Format:
    def __init__(self, header: bytes, ext: str, aes_key: Optional[bytes] = None):
        self.Header = header
        self.Ext = ext
        self.AesKey = aes_key

JPG = Format(header=b"\xFF\xD8\xFF", ext="jpg")
PNG = Format(header=b"\x89PNG", ext="png")
GIF = Format(header=b"GIF8", ext="gif")
TIFF = Format(header=b"II*\x00", ext="tiff")
BMP = Format(header=b"BM", ext="bmp")
WXGF = Format(header=b"wxgf", ext="wxgf")
FORMATS = [JPG, PNG, GIF, TIFF, BMP, WXGF]

V4_FORMAT1 = Format(header=b"\x07\x08\x56\x31", ext="dat", aes_key=b"cfcd208495d565ef")
V4_FORMAT2 = Format(header=b"\x07\x08\x56\x32", ext="dat", aes_key=b"0000000000000000")
V4_FORMATS = [V4_FORMAT1, V4_FORMAT2]

# Globals
v4_xor_key: int = 0x37
v4_format2_header = V4_FORMAT2.Header


def set_aes_key(hex_key: str) -> None:
    global V4_FORMAT2
    if not hex_key:
        return
    try:
        V4_FORMAT2.AesKey = bytes.fromhex(hex_key)
    except Exception:
        pass


def decrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_ECB)
    if len(data) % 16 != 0:
        raise ValueError("data length must be multiple of 16")
    out = bytearray(len(data))
    for i in range(0, len(data), 16):
        out[i:i+16] = cipher.decrypt(data[i:i+16])
    # PKCS#7 strip if valid
    if out:
        pad = out[-1]
        if 0 < pad <= 16 and all(b == pad for b in out[-pad:]):
            return bytes(out[:-pad])
    return bytes(out)


def dat2image_v4(data: bytes, aes_key: bytes) -> Tuple[bytes, str]:
    if len(data) < 15:
        raise ValueError("data too short for v4 dat")
    aes_len = struct.unpack_from('<I', data, 6)[0]
    xor_len = struct.unpack_from('<I', data, 10)[0]
    payload = data[15:]
    aes_len0 = (aes_len // 16) * 16 + 16
    aes_len0 = min(aes_len0, len(payload))

    dec = decrypt_aes_ecb(payload[:aes_len0], aes_key)
    result = bytearray()
    result += dec[:aes_len]
    mid_start = aes_len0
    mid_end = len(payload) - xor_len
    if mid_start < mid_end:
        result += payload[mid_start:mid_end]
    if xor_len > 0 and mid_end < len(payload):
        tail = payload[mid_end:]
        result += bytes([b ^ v4_xor_key for b in tail])

    head = bytes(result[:4])
    if head.startswith(WXGF.Header):
        from .wxgf import wxam2pic
        return wxam2pic(bytes(result))
    for f in FORMATS:
        if result.startswith(f.Header):
            return bytes(result), f.Ext
    raise ValueError("unknown image type after decryption")


def dat2image(data: bytes) -> Tuple[bytes, str]:
    if len(data) < 4:
        raise ValueError("data too short")
    for f in V4_FORMATS:
        if data.startswith(f.Header):
            return dat2image_v4(data, f.AesKey or b"")

    # legacy xor detection
    xor = data[0] ^ JPG.Header[0]
    for h in [JPG.Header, PNG.Header, GIF.Header, TIFF.Header, BMP.Header]:
        x = data[0] ^ h[0]
        if all((data[i] ^ h[i]) == x for i in range(len(h))):
            out = bytes(b ^ x for b in data)
            for f in FORMATS:
                if out.startswith(f.Header):
                    return out, f.Ext
    raise ValueError("unknown image type")


def scan_and_set_xor_key(dir_path: str) -> int:
    global v4_xor_key
    for root, _, files in os.walk(dir_path):
        for name in files:
            if not name.endswith('_t.dat'):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, 'rb') as f:
                    data = f.read()
            except Exception:
                continue
            if len(data) < 6 or (not data.startswith(V4_FORMAT1.Header) and not data.startswith(V4_FORMAT2.Header)):
                continue
            if len(data) < 17:
                continue
            xor_len = struct.unpack_from('<I', data, 10)[0]
            tail = data[15:]
            if xor_len == 0 or xor_len > len(tail):
                continue
            xor_data = tail[len(tail)-xor_len:]
            if len(xor_data) >= 2:
                jpg_tail = b"\xFF\xD9"
                keys = bytes([xor_data[-2] ^ jpg_tail[0], xor_data[-1] ^ jpg_tail[1]])
                if keys[0] == keys[1]:
                    v4_xor_key = keys[0]
                    return v4_xor_key
    return v4_xor_key
