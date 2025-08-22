import os
import struct
import hashlib
import hmac
from typing import Optional

try:
    from Crypto.Cipher import AES  # pycryptodome
except ImportError as e:
    raise RuntimeError("pycryptodome is required. Please install with: pip install pycryptodome") from e


# Common constants (mirroring internal/wechat/decrypt/common)
KEY_SIZE = 32
SALT_SIZE = 16
AES_BLOCK_SIZE = 16
SQLITE_HEADER = b"SQLite format 3\x00"
IV_SIZE = 16

# Windows v4 decryptor params
V4_ITER_COUNT = 256000
HMAC_SHA512_SIZE = 64
PAGE_SIZE = 4096
RESERVE = IV_SIZE + HMAC_SHA512_SIZE  # 16 + 64 = 80, already multiple of 16

# Image signatures
JPG_HEADER = b"\xFF\xD8\xFF"
WXGF_HEADER = b"wxgf"

# WeChat v4 dat header for AES-format-2 (07085632)
V4_FORMAT2_HEADER = b"\x07\x08\x56\x32"


def _xor_bytes(b: bytes, x: int) -> bytes:
    return bytes([v ^ x for v in b])


class DBValidator:
    def __init__(self, data_dir: str):
        # Windows v4 simple db file path
        # internal/wechat/decrypt/validator.go -> GetSimpleDBFile: db_storage\\message\\message_0.db
        self.db_path = os.path.join(data_dir, "db_storage", "message", "message_0.db")
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"DB file not found: {self.db_path}")

        # Read first page and salt
        with open(self.db_path, "rb") as f:
            self.first_page = f.read(PAGE_SIZE)
        if len(self.first_page) < PAGE_SIZE:
            raise IOError(f"Failed to read first page: expected {PAGE_SIZE}, got {len(self.first_page)}")
        if self.first_page.startswith(SQLITE_HEADER[:-1]):
            # Already decrypted; for key validation we treat as invalid context
            raise ValueError("Database already decrypted; cannot validate encrypted key against plain DB")

        self.salt = self.first_page[:SALT_SIZE]

    @staticmethod
    def _derive_keys(db_key: bytes, salt: bytes) -> tuple[bytes, bytes]:
        # encKey = PBKDF2-HMAC(SHA512, key, salt, 256000, 32)
        enc_key = hashlib.pbkdf2_hmac('sha512', db_key, salt, V4_ITER_COUNT, KEY_SIZE)
        # macKey = PBKDF2-HMAC(SHA512, encKey, xor(salt, 0x3a), 2, 32)
        mac_salt = _xor_bytes(salt, 0x3a)
        mac_key = hashlib.pbkdf2_hmac('sha512', enc_key, mac_salt, 2, KEY_SIZE)
        return enc_key, mac_key

    def validate_db_key(self, key_bytes: bytes) -> bool:
        if len(key_bytes) != KEY_SIZE:
            return False

        _, mac_key = self._derive_keys(key_bytes, self.salt)

        # HMAC over page1[SaltSize:dataEnd] || little_endian(uint32(1))
        data_end = PAGE_SIZE - RESERVE + IV_SIZE
        mac = hmac.new(mac_key, self.first_page[SALT_SIZE:data_end], hashlib.sha512)
        mac.update(struct.pack('<I', 1))
        calculated = mac.digest()
        stored = self.first_page[data_end:data_end + HMAC_SHA512_SIZE]
        return hmac.compare_digest(calculated, stored)


class ImgKeyValidator:
    def __init__(self, data_dir: str):
        self.encrypted_block: Optional[bytes] = None
        # Walk data_dir recursively to find first suitable .dat (exclude *_t.dat)
        for root, _, files in os.walk(data_dir):
            for name in files:
                if not name.endswith('.dat') or name.endswith('_t.dat'):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, 'rb') as f:
                        data = f.read(15 + AES_BLOCK_SIZE)
                except Exception:
                    continue
                if len(data) >= 15 + AES_BLOCK_SIZE and data[:4] == V4_FORMAT2_HEADER:
                    self.encrypted_block = data[15:15 + AES_BLOCK_SIZE]
                    return

    def validate_img_key(self, key_bytes: bytes) -> bool:
        if self.encrypted_block is None or len(key_bytes) < 16:
            return False
        aes_key = key_bytes[:16]
        try:
            cipher = AES.new(aes_key, AES.MODE_ECB)
            decrypted = cipher.decrypt(self.encrypted_block)
        except Exception:
            return False
        return decrypted.startswith(JPG_HEADER) or decrypted.startswith(WXGF_HEADER)
