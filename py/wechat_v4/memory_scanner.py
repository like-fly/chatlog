import ctypes
import platform
import subprocess
import os
import tempfile
import time
import re
from typing import Iterator, Optional, Tuple

# Windows V4 pointer search pattern (used on Windows only)
KEY_PATTERN = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x2F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])

# Platform detection
def _is_macos() -> bool:
    return platform.system() == 'Darwin'


def _is_windows() -> bool:
    return platform.system() == 'Windows'


class WindowsMemoryAPI:
    """Windows-specific memory access API wrapper."""
    def __init__(self):
        if not _is_windows():
            raise RuntimeError("Windows API not available on this platform")
        
        # Import Windows modules only when needed
        try:
            import ctypes.wintypes as wt
            self.wt = wt
            
            # Constants
            self.PROCESS_VM_READ = 0x0010
            self.PROCESS_QUERY_INFORMATION = 0x0400
            self.MEM_COMMIT = 0x1000
            self.MEM_PRIVATE = 0x20000
            self.PAGE_READWRITE = 0x04
            
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
            
            self.MEMORY_BASIC_INFORMATION = MEMORY_BASIC_INFORMATION
            
            # API functions - delay windll access until init
            kernel32 = ctypes.WinDLL('kernel32')
            
            self.OpenProcess = kernel32.OpenProcess
            self.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
            self.OpenProcess.restype = wt.HANDLE
            
            self.ReadProcessMemory = kernel32.ReadProcessMemory
            self.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            self.ReadProcessMemory.restype = wt.BOOL
            
            self.VirtualQueryEx = kernel32.VirtualQueryEx
            self.VirtualQueryEx.argtypes = [wt.HANDLE, wt.LPCVOID, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
            self.VirtualQueryEx.restype = ctypes.c_size_t
            
            self.CloseHandle = kernel32.CloseHandle
            self.CloseHandle.argtypes = [wt.HANDLE]
            self.CloseHandle.restype = wt.BOOL
            
        except (ImportError, AttributeError) as e:
            raise RuntimeError(f"Failed to initialize Windows API: {e}")

    def _voidp_to_int(self, p) -> int:
        v = ctypes.cast(p, ctypes.c_void_p).value
        return int(v or 0)

    def enum_regions(self, process_handle: int) -> Iterator[Tuple[int, int, int]]:
        """Enumerate memory regions on Windows."""
        address = 0x10000
        max_addr = 0x7FFFFFFFFFFF
        mbi = self.MEMORY_BASIC_INFORMATION()
        
        while address < max_addr:
            res = self.VirtualQueryEx(self.wt.HANDLE(process_handle), self.wt.LPCVOID(address), 
                                    ctypes.byref(mbi), ctypes.sizeof(mbi))
            if res == 0:
                break
                
            region_size = int(mbi.RegionSize)
            base_addr = self._voidp_to_int(mbi.BaseAddress)
            
            # Skip small regions (<1MB) and very large regions (>512MB) for performance
            if (region_size >= 1024 * 1024 and region_size <= 512 * 1024 * 1024 and
                mbi.State == self.MEM_COMMIT and 
                (mbi.Protect & self.PAGE_READWRITE) and 
                mbi.Type == self.MEM_PRIVATE):
                # Limit individual chunks to 64MB to match earlier working version
                max_chunk_size = 64 * 1024 * 1024
                if region_size <= max_chunk_size:
                    yield (base_addr, region_size, int(mbi.Protect))
                else:
                    # Split large regions into smaller chunks (max 3 chunks per region)
                    for chunk_start in range(0, min(region_size, 3 * max_chunk_size), max_chunk_size):
                        chunk_size = min(max_chunk_size, region_size - chunk_start)
                        yield (base_addr + chunk_start, chunk_size, int(mbi.Protect))
                
            # Advance to next region
            next_addr = base_addr + region_size
            if next_addr <= address:
                next_addr = address + region_size
            address = next_addr

    def read_memory(self, handle: int, base: int, size: int) -> Optional[bytes]:
        """Read memory from a Windows process."""
        buf = (ctypes.c_ubyte * size)()
        read = ctypes.c_size_t(0)
        ok = self.ReadProcessMemory(self.wt.HANDLE(handle), self.wt.LPCVOID(base), 
                                  ctypes.byref(buf), size, ctypes.byref(read))
        if not ok:
            return None
        return bytes(buf[:int(read.value)])

    def open_process(self, pid: int) -> int:
        """Open a Windows process."""
        h = self.OpenProcess(self.PROCESS_VM_READ | self.PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            raise OSError("OpenProcess failed")
        return h

    def close_handle(self, h: int) -> None:
        """Close a Windows process handle."""
        if h:
            self.CloseHandle(self.wt.HANDLE(h))


class MacOSMemoryAPI:
    """macOS-specific memory access API wrapper."""
    def __init__(self):
        if not _is_macos():
            raise RuntimeError("macOS API not available on this platform")
        
        self.FILTER_REGION_TYPE = "MALLOC_NANO"
        self.FILTER_SHRMOD = "SM=PRV"
        # Regex matches vmmap writable section rows, similar to Go
        self._vmmap_row_re = re.compile(r"^(\S+)\s+([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+\[\s*(\S+)\s+(\S+)(?:\s+\S+){2}\]\s+(\S+)\s+(\S+)(?:\s+\S+)?\s+(.*)$")

    def check_sip_disabled(self) -> bool:
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

    def get_vmmap_regions(self, pid: int) -> list:
        """Get memory regions from vmmap command on macOS (writable section)."""
        try:
            result = subprocess.run(['vmmap', '-wide', str(pid)], capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return []
            
            regions = []
            lines = result.stdout.splitlines()

            # Find the 'Writable regions' header as in Go implementation
            header_index = -1
            for i, line in enumerate(lines):
                if line.startswith('==== Writable regions for'):
                    header_index = i
                    break
            if header_index == -1:
                return []

            # Skip the next header line with columns if present
            i = header_index + 1
            if i < len(lines) and ('REGION TYPE' in lines[i] or 'REGION TYPE' in lines[i].upper()):
                i += 1

            # Parse rows
            while i < len(lines):
                line = lines[i].strip()
                i += 1
                if not line:
                    continue
                m = self._vmmap_row_re.match(line)
                if not m:
                    continue

                region_type = m.group(1)
                start_addr = int(m.group(2), 16)
                end_addr = int(m.group(3), 16)
                # vsize = m.group(4)  # not used here
                # rsdnt = m.group(5)  # not used here
                perms = m.group(6)
                shrmod = m.group(7)
                # detail = m.group(8)

                # Filter like Go: RegionType MALLOC_NANO
                if region_type != self.FILTER_REGION_TYPE:
                    continue
                # Note: Go filter doesn't require SM=PRV explicitly

                size = end_addr - start_addr
                if size >= 1024 * 1024:
                    regions.append({
                        'start': start_addr,
                        'end': end_addr,
                        'size': size,
                        'type': region_type,
                        'perms': perms,
                        'shrmod': shrmod,
                    })
            return regions
        except Exception:
            return []

    def enum_regions(self, pid: int) -> Iterator[Tuple[int, int, int]]:
        """Enumerate memory regions on macOS."""
        regions = self.get_vmmap_regions(pid)
        for region in regions:
            yield (region['start'], region['size'], 0)  # protect not used on macOS

    def read_memory(self, pid: int, start_addr: int, size: int) -> Optional[bytes]:
        """Read memory from a process on macOS using lldb - single unified read like Go."""
        try:
            # Create temporary pipe for data transfer
            pipe_path = os.path.join(tempfile.gettempdir(), f"chatlog_pipe_{int(time.time() * 1000000)}")
            
            # Create named pipe
            subprocess.run(['mkfifo', pipe_path], check=True, timeout=5)
            
            # Start goroutine-like reader for pipe data
            import threading
            data_result: list[Optional[bytes]] = [None]
            error_result: list[Optional[Exception]] = [None]
            
            def read_pipe():
                try:
                    with open(pipe_path, 'rb') as pipe_file:
                        data_result[0] = pipe_file.read()
                except Exception as e:
                    error_result[0] = e
            
            reader_thread = threading.Thread(target=read_pipe)
            reader_thread.start()
            
            try:
                # Prepare lldb command with sudo - like Go's approach but with elevated privileges
                lldb_cmd = (f'sudo lldb -p {pid} -o "memory read --binary --force --outfile {pipe_path} '
                           f'--count {size} 0x{start_addr:x}" -o "quit"')
                
                # Start lldb process
                lldb_process = subprocess.Popen(['bash', '-c', lldb_cmd], 
                                              stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
                
                # Wait for reader with timeout (30s like Go)
                reader_thread.join(timeout=30)
                
                if reader_thread.is_alive():
                    # Timeout occurred
                    lldb_process.kill()
                    return None
                
                # Wait for lldb to finish
                try:
                    lldb_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    lldb_process.kill()
                
                # Return result
                if error_result[0]:
                    return None
                return data_result[0] if data_result[0] else None
                
            finally:
                # Clean up pipe
                try:
                    os.unlink(pipe_path)
                except OSError:
                    pass
                    
        except Exception:
            return None

    def open_process(self, pid: int) -> int:
        """Open a process for memory access on macOS."""
        # Check SIP status first
        if not self.check_sip_disabled():
            raise OSError("System Integrity Protection (SIP) must be disabled to read process memory on macOS")
        return pid  # On macOS, we just return the PID as the "handle"

    def close_handle(self, h: int) -> None:
        """Close a process handle on macOS."""
        # On macOS, nothing to close since we use PID directly
        pass


# Global API instance
_memory_api = None

def _get_memory_api():
    """Get the appropriate memory API for the current platform."""
    global _memory_api
    if _memory_api is None:
        if _is_windows():
            _memory_api = WindowsMemoryAPI()
        elif _is_macos():
            _memory_api = MacOSMemoryAPI()
        else:
            raise NotImplementedError("Unsupported platform")
    return _memory_api


# Cross-platform interface functions
def enum_regions(process: int) -> Iterator[Tuple[int, int, int]]:
    """Enumerate memory regions - cross-platform implementation."""
    api = _get_memory_api()
    yield from api.enum_regions(process)


def read_memory(handle: int, base: int, size: int) -> Optional[bytes]:
    """Read memory from a process - cross-platform implementation."""
    api = _get_memory_api()
    return api.read_memory(handle, base, size)


def search_keys_in_region(block: bytes) -> Iterator[int]:
    """Search for key patterns in a memory block (Windows V4 pointer scan)."""
    # Early exit if block is too small
    if len(block) < len(KEY_PATTERN) + 8:
        return
        
    # Search from end like Go code, but with optimizations
    block_len = len(block)
    pattern_len = len(KEY_PATTERN)
    
    # Pre-calculate to avoid repeated calculations
    min_ptr = 0x10000
    max_ptr = 0x7FFFFFFFFFFF
    found_ptrs = set()  # Avoid duplicate pointers
    
    # Simple search from end like Go code - restore original logic
    idx = block_len
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
    api = _get_memory_api()
    return api.open_process(pid)


def close_handle(h: int) -> None:
    """Close a process handle - cross-platform implementation."""
    api = _get_memory_api()
    api.close_handle(h)


def read_key_bytes(handle: int, addr: int, length: int = 32) -> Optional[bytes]:
    """Read key bytes from memory - cross-platform implementation."""
    return read_memory(handle, addr, length)
