import os
from typing import Optional

try:
    from Crypto.Cipher import AES
except ImportError as e:
    raise RuntimeError("pycryptodome is required. Please install with: pip install pycryptodome") from e

JPG_HEADER = b"\xFF\xD8\xFF"
WXGF_HEADER = b"wxgf"
V4_FORMAT2_HEADER = b"\x07\x08\x56\x32"


class AesKeyValidator:
    def __init__(self, path: str):
        self.Path = path
        self.EncryptedData: Optional[bytes] = None
        for root, _, files in os.walk(path):
            for name in files:
                if not name.endswith('.dat') or name.endswith('_t.dat'):
                    continue
                p = os.path.join(root, name)
                try:
                    with open(p, 'rb') as f:
                        data = f.read(15 + 16)
                except Exception:
                    continue
                if len(data) >= 31 and data[:4] == V4_FORMAT2_HEADER:
                    self.EncryptedData = data[15:31]
                    return

    def Validate(self, key: bytes) -> bool:
        if not self.EncryptedData or len(key) < 16:
            return False
        k = key[:16]
        try:
            cipher = AES.new(k, AES.MODE_ECB)
            dec = cipher.decrypt(self.EncryptedData)
        except Exception:
            return False
        return dec.startswith(JPG_HEADER) or dec.startswith(WXGF_HEADER)
