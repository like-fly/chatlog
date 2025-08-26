import binascii
import platform
from typing import Optional, Tuple, Set

from .process_detector import find_wechat_v4_processes
from . import memory_scanner as ms  # use package-level alias for fallback
from .validator import DBValidator, ImgKeyValidator


# macOS V4 search patterns (mirroring internal/wechat/key/darwin/v4.go)
_V4_DATA_PATTERNS = [
    # Pattern: 0x20 'f' 't' 's' '5' '(' '%' 0x00, Offsets: 16, -80, 64
    (b"\x20fts5(%\x00", [16, -80, 64]),
]
_V4_IMG_ZERO16 = b"\x00" * 16
_V4_IMG_OFFSETS = [-32]


def _search_data_key_block_mac(memory: bytes, db_validator: Optional[DBValidator], processed_hex: Set[str]) -> Optional[str]:
    if not db_validator:
        return None
    
    for pattern, offsets in _V4_DATA_PATTERNS:
        index = len(memory)
        while True:
            index = memory.rfind(pattern, 0, index)
            if index == -1:
                break
                
            for off in offsets:
                key_off = index + off
                if key_off < 0 or key_off + 32 > len(memory):
                    continue
                key_bytes = memory[key_off:key_off+32]
                key_hex = binascii.hexlify(key_bytes).decode()
                if key_hex in processed_hex:
                    continue
                processed_hex.add(key_hex)
                if db_validator.validate_db_key(key_bytes):
                    return key_hex
            index -= 1
    return None


def _search_img_key_block_mac(memory: bytes, img_validator: Optional[ImgKeyValidator], processed_hex: Set[str]) -> Optional[str]:
    if not img_validator:
        return None
    
    zero_pattern = _V4_IMG_ZERO16
    memory_size = len(memory)
    
    # 简单的从后往前搜索零模式，类似Go的实现
    index = memory_size
    while True:
        index = memory.rfind(zero_pattern, 0, index)
        if index == -1:
            break
            
        # 尝试offset -32
        for off in _V4_IMG_OFFSETS:
            key_off = index + off
            if key_off < 0 or key_off + 16 > memory_size:
                continue
                
            key_bytes16 = memory[key_off:key_off+16]
            if key_bytes16 == zero_pattern:
                continue
                
            key_hex = binascii.hexlify(key_bytes16).decode()
            if key_hex in processed_hex:
                continue
                
            processed_hex.add(key_hex)
            
            # 验证密钥
            if img_validator.validate_img_key(key_bytes16):
                return key_hex
        
        index -= 1
    
    return None


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

    h = ms.open_process(proc.pid)
    data_hex: Optional[str] = None
    img_hex: Optional[str] = None

    try:
        # Use the same logic for both platforms - simple region-by-region search
        for base, size, _ in ms.enum_regions(h):
            block = ms.read_memory(h, base, size)
            if not block:
                continue
                
            if platform.system() == 'Darwin':
                # macOS: Use direct pattern search in each memory region
                processed_data: Set[str] = set()
                processed_img: Set[str] = set()
                
                # Search for data key patterns
                if not data_hex:
                    found_data = _search_data_key_block_mac(block, db_validator, processed_data)
                    if found_data:
                        data_hex = found_data
                        
                # Search for image key patterns  
                if not img_hex:
                    found_img = _search_img_key_block_mac(block, img_validator, processed_img)
                    if found_img:
                        img_hex = found_img
                        
            else:
                # Windows: Use pointer-chasing search
                for ptr in ms.search_keys_in_region(block):
                    key_bytes = ms.read_key_bytes(h, ptr, 32)
                    if not key_bytes:
                        continue
                    # DB key check (32 bytes)
                    if not data_hex and db_validator and db_validator.validate_db_key(key_bytes):
                        data_hex = binascii.hexlify(key_bytes).decode()
                    # Image key check (first 16 bytes)
                    if not img_hex and img_validator and img_validator.validate_img_key(key_bytes[:16]):
                        img_hex = binascii.hexlify(key_bytes[:16]).decode()
                        
            # Check if both keys found
            if data_hex and img_hex:
                return data_hex, img_hex
                
        return data_hex, img_hex
    finally:
        ms.close_handle(h)
