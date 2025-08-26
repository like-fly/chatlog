import ctypes
import ctypes.wintypes as wt
import platform
import subprocess
import os
import tempfile
import time
from typing import Iterator, Optional, Tuple

# Windows constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04

# macOS constants
FILTER_REGION_TYPE = "MALLOC_NANO"
FILTER_SHRMOD = "SM=PRV"

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


# Platform-specific implementations
def _is_macos() -> bool:
    return platform.system() == 'Darwin'


def _is_windows() -> bool:
    return platform.system() == 'Windows'


# Windows structures and functions
if _is_windows():
    try:
        import ctypes.wintypes as wt
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
    except (AttributeError, ImportError):
        # Not on Windows or Windows DLLs not available
        pass


# macOS helper functions
def _check_sip_disabled() -> bool:
    """Check if System Integrity Protection (SIP) is disabled on macOS."""
    try:
        result = subprocess.run(['csrutil', 'status'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False
        output = result.stdout.lower()
        return ('system integrity protection status: disabled' in output or 
                ('disabled' in output and 'debugging' in output))
    except Exception:
        return False


def _get_vmmap_regions(pid: int) -> list:
    """Get memory regions from vmmap command on macOS."""
    try:
        result = subprocess.run(['vmmap', '-wide', str(pid)], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        
        regions = []
        lines = result.stdout.split('\n')
        
        # Find header line and start parsing
        header_found = False
        for line in lines:
            if not header_found:
                if 'Virtual Memory Map of process' in line or 'Region Type' in line:
                    header_found = True
                continue
            
            # Skip empty lines and non-data lines
            if not line.strip() or '=====' in line:
                continue
                
            # Parse region line
            parts = line.split()
            if len(parts) < 6:
                continue
                
            try:
                # Extract region info - format varies, but generally:
                # MALLOC_NANO    [address range]  [size]  [perms]  SM=PRV  
                region_type = parts[0]
                address_range = parts[1] if len(parts) > 1 else ""
                
                # Skip non-MALLOC_NANO regions
                if region_type != FILTER_REGION_TYPE:
                    continue
                    
                # Check if it's private memory (SM=PRV)
                if FILTER_SHRMOD not in line:
                    continue
                    
                # Parse address range
                if '-' in address_range:
                    start_str, end_str = address_range.split('-')
                    start_addr = int(start_str, 16)
                    end_addr = int(end_str, 16)
                    size = end_addr - start_addr
                    
                    # Only include regions >= 1MB
                    if size >= 1024 * 1024:
                        regions.append({
                            'start': start_addr,
                            'end': end_addr,
                            'size': size,
                            'type': region_type
                        })
            except (ValueError, IndexError):
                continue
                
        return regions
    except Exception:
        return []


def _read_memory_macos(pid: int, start_addr: int, size: int) -> Optional[bytes]:
    """Read memory from a process on macOS using lldb."""
    try:
        # Create temporary pipe for data transfer
        pipe_path = os.path.join(tempfile.gettempdir(), f"chatlog_pipe_{int(time.time() * 1000000)}")
        
        # Create named pipe
        subprocess.run(['mkfifo', pipe_path], check=True, timeout=5)
        
        try:
            # Prepare lldb command
            lldb_cmd = (f'lldb -p {pid} -o "memory read --binary --force --outfile {pipe_path} '
                       f'--count {size} 0x{start_addr:x}" -o "quit"')
            
            # Start lldb process
            lldb_process = subprocess.Popen(['bash', '-c', lldb_cmd], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE)
            
            # Read from pipe with timeout
            try:
                with open(pipe_path, 'rb') as pipe_file:
                    data = pipe_file.read()
                    return data if data else None
            except Exception:
                return None
            finally:
                # Wait for lldb to finish (with timeout)
                try:
                    lldb_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    lldb_process.kill()
        finally:
            # Clean up pipe
            try:
                os.unlink(pipe_path)
            except OSError:
                pass
                
    except Exception:
        return None


def _voidp_to_int(p) -> int:
    v = ctypes.cast(p, ctypes.c_void_p).value
    return int(v or 0)


def enum_regions(process: int) -> Iterator[Tuple[int, int, int]]:
    """Enumerate memory regions - cross-platform implementation."""
    if _is_windows():
        yield from _enum_regions_windows(process)
    elif _is_macos():
        yield from _enum_regions_macos(process)
    else:
        raise NotImplementedError("Unsupported platform")


def _enum_regions_windows(process: int) -> Iterator[Tuple[int, int, int]]:
    """Windows-specific memory region enumeration."""
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


def _enum_regions_macos(process: int) -> Iterator[Tuple[int, int, int]]:
    """macOS-specific memory region enumeration."""
    regions = _get_vmmap_regions(process)
    for region in regions:
        yield (region['start'], region['size'], 0)  # protect not used on macOS
def read_memory(handle: int, base: int, size: int) -> Optional[bytes]:
    """Read memory from a process - cross-platform implementation."""
    if _is_windows():
        return _read_memory_windows(handle, base, size)
    elif _is_macos():
        # For macOS, handle is actually the PID
        return _read_memory_macos(handle, base, size)
    else:
        raise NotImplementedError("Unsupported platform")


def _read_memory_windows(handle: int, base: int, size: int) -> Optional[bytes]:
    """Windows-specific memory reading."""
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
    """Open a process for memory access - cross-platform implementation."""
    if _is_windows():
        return _open_process_windows(pid)
    elif _is_macos():
        # Check SIP status first
        if not _check_sip_disabled():
            raise OSError("System Integrity Protection (SIP) must be disabled to read process memory on macOS")
        return pid  # On macOS, we just return the PID as the "handle"
    else:
        raise NotImplementedError("Unsupported platform")


def _open_process_windows(pid: int) -> int:
    """Windows-specific process opening."""
    h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError("OpenProcess failed")
    return h


def close_handle(h: int) -> None:
    """Close a process handle - cross-platform implementation."""
    if _is_windows() and h:
        CloseHandle(wt.HANDLE(h))
    # On macOS, nothing to close since we use PID directly


def read_key_bytes(handle: int, addr: int, length: int = 32) -> Optional[bytes]:
    """Read key bytes from memory - cross-platform implementation."""
    return read_memory(handle, addr, length)
