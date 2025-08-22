import binascii
from typing import Optional, Tuple

from .process_detector import find_wechat_v4_processes
from .memory_scanner import open_process, close_handle, enum_regions, read_memory, search_keys_in_region, read_key_bytes
from .validator import DBValidator, ImgKeyValidator


def extract_keys() -> Tuple[Optional[str], Optional[str]]:
    procs = find_wechat_v4_processes()
    if not procs:
        return None, None
    # Use the first online process with data_dir
    proc = next((p for p in procs if p.status == 'online' and p.data_dir), procs[0])

    db_validator: Optional[DBValidator] = None
    img_validator: Optional[ImgKeyValidator] = None
    if proc.data_dir:
        try:
            db_validator = DBValidator(proc.data_dir)
        except Exception:
            db_validator = None
        try:
            img_validator = ImgKeyValidator(proc.data_dir)
        except Exception:
            img_validator = None

    h = open_process(proc.pid)
    data_hex: Optional[str] = None
    img_hex: Optional[str] = None
    try:
        for base, size, _ in enum_regions(h):
            block = read_memory(h, base, size)
            if not block:
                continue
            for ptr in search_keys_in_region(block):
                key_bytes = read_key_bytes(h, ptr, 32)
                if not key_bytes:
                    continue
                # DB key check (32 bytes)
                if not data_hex and db_validator and db_validator.validate_db_key(key_bytes):
                    data_hex = binascii.hexlify(key_bytes).decode()
                # Image key check (first 16 bytes)
                if not img_hex and img_validator and img_validator.validate_img_key(key_bytes):
                    img_hex = binascii.hexlify(key_bytes[:16]).decode()
                if data_hex and img_hex:
                    return data_hex, img_hex
        return data_hex, img_hex
    finally:
        close_handle(h)
