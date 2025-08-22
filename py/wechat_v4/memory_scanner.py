import ctypes
import ctypes.wintypes as wt
from typing import Iterator, Optional, Tuple

# Windows constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04

# Structures
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", wt.LPVOID),
        ("AllocationBase", wt.LPVOID),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


kernel32 = ctypes.windll.kernel32

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
ReadProcessMemory.restype = wt.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [wt.HANDLE, wt.LPCVOID, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
VirtualQueryEx.restype = ctypes.c_size_t

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wt.HANDLE]
CloseHandle.restype = wt.BOOL


def _voidp_to_int(p) -> int:
    v = ctypes.cast(p, ctypes.c_void_p).value
    return int(v or 0)


def enum_regions(process: int) -> Iterator[Tuple[int, int, int]]:
    # Yields (base_address, region_size, protect)
    address = 0x10000
    max_addr = 0x7FFFFFFFFFFF
    mbi = MEMORY_BASIC_INFORMATION()
    while address < max_addr:
        res = VirtualQueryEx(wt.HANDLE(process), wt.LPCVOID(address), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if res == 0:
            break
        region_size = int(mbi.RegionSize)
        base_addr = _voidp_to_int(mbi.BaseAddress)
        # Skip small regions (<1MB)
        if region_size >= 1024 * 1024 and mbi.State == MEM_COMMIT and (mbi.Protect & PAGE_READWRITE) and mbi.Type == MEM_PRIVATE:
            yield (base_addr, region_size, int(mbi.Protect))
        # Advance to next region
        next_addr = base_addr + region_size
        if next_addr <= address:
            next_addr = address + region_size
        address = next_addr


def read_memory(handle: int, base: int, size: int) -> Optional[bytes]:
    buf = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t(0)
    ok = ReadProcessMemory(wt.HANDLE(handle), wt.LPCVOID(base), ctypes.byref(buf), size, ctypes.byref(read))
    if not ok:
        return None
    return bytes(buf[: int(read.value)])


KEY_PATTERN = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x2F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])


def search_keys_in_region(block: bytes) -> Iterator[int]:
    # Search from end like Go code
    idx = len(block)
    while True:
        idx = block.rfind(KEY_PATTERN, 0, idx)
        if idx == -1 or idx - 8 < 0:
            break
        ptr = int.from_bytes(block[idx - 8:idx], 'little')
        if 0x10000 < ptr < 0x7FFFFFFFFFFF:
            yield ptr
        idx -= 1


def open_process(pid: int) -> int:
    h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError("OpenProcess failed")
    return h


def close_handle(h: int) -> None:
    if h:
        CloseHandle(wt.HANDLE(h))


def read_key_bytes(handle: int, addr: int, length: int = 32) -> Optional[bytes]:
    return read_memory(handle, addr, length)
