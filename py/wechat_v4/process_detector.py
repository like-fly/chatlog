import os
import psutil
import platform
import subprocess
import plistlib
from dataclasses import dataclass
from typing import List, Optional, Tuple
import ctypes
import ctypes.wintypes as wt

V4_PROCESS_NAME = "Weixin"
V4_DB_REL = os.path.join("db_storage", "session", "session.db")

# macOS constants
MAC_PROCESS_NAME_OFFICIAL = "WeChat"
MAC_PROCESS_NAME_BETA = "Weixin"
MAC_V3_DB_REL = os.path.join("Message", "msg_0.db")
MAC_V4_DB_REL = os.path.join("db_storage", "session", "session.db")


# VS_FIXEDFILEINFO structure (Windows)
class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wt.DWORD),
        ("dwStrucVersion", wt.DWORD),
        ("dwFileVersionMS", wt.DWORD),
        ("dwFileVersionLS", wt.DWORD),
        ("dwProductVersionMS", wt.DWORD),
        ("dwProductVersionLS", wt.DWORD),
        ("dwFileFlagsMask", wt.DWORD),
        ("dwFileFlags", wt.DWORD),
        ("dwFileOS", wt.DWORD),
        ("dwFileType", wt.DWORD),
        ("dwFileSubtype", wt.DWORD),
        ("dwFileDateMS", wt.DWORD),
        ("dwFileDateLS", wt.DWORD),
    ]


def _get_file_version(path: str) -> Optional[str]:
    # Windows only
    try:
        ver = ctypes.windll.version
        handle = wt.DWORD(0)
        size = ver.GetFileVersionInfoSizeW(path, ctypes.byref(handle))
        if size == 0:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return None
        lptr = wt.LPVOID()
        ulen = wt.UINT(0)
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(lptr), ctypes.byref(ulen)):
            return None
        if not lptr:
            return None
        ffi_ptr = ctypes.cast(lptr, ctypes.POINTER(VS_FIXEDFILEINFO))
        ffi = ffi_ptr.contents

        def HIWORD(d: int) -> int:
            return (d >> 16) & 0xFFFF

        def LOWORD(d: int) -> int:
            return d & 0xFFFF

        major = HIWORD(ffi.dwFileVersionMS)
        minor = LOWORD(ffi.dwFileVersionMS)
        build = HIWORD(ffi.dwFileVersionLS)
        revision = LOWORD(ffi.dwFileVersionLS)
        return f"{major}.{minor}.{build}.{revision}"
    except Exception:
        return None


# macOS helpers
def _plist_version_from_exe(exe_path: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        # exe: /Applications/WeChat.app/Contents/MacOS/WeChat
        contents_dir = os.path.dirname(os.path.dirname(exe_path))  # .../Contents
        info_plist = os.path.join(contents_dir, "Info.plist")
        with open(info_plist, "rb") as f:
            pl = plistlib.load(f)
        full = pl.get("CFBundleShortVersionString")
        if not full:
            return None, None
        major_str = str(full).split(".")[0]
        try:
            major = int(major_str)
        except Exception:
            major = None
        return major, full
    except Exception:
        return None, None


def _lsof_open_files(pid: int) -> List[str]:
    try:
        # lsof -p <pid> -F n
        out = subprocess.check_output(["lsof", "-p", str(pid), "-F", "n"], stderr=subprocess.DEVNULL)
        lines = out.decode(errors="ignore").splitlines()
        files = []
        for line in lines:
            if line.startswith("n"):
                p = line[1:]
                if p:
                    files.append(p)
        return files
    except Exception:
        return []


@dataclass
class WeChatProcess:
    pid: int
    exe_path: str
    version: int
    status: str
    data_dir: Optional[str]
    account_name: Optional[str]
    full_version: Optional[str] = None


def _strip_exe(name: str) -> str:
    return name[:-4] if name.lower().endswith('.exe') else name


# Windows implementation (v4 only)
def _find_windows_v4() -> List[WeChatProcess]:
    results: List[WeChatProcess] = []
    for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'open_files']):
        try:
            name = _strip_exe(p.info.get('name') or '')
            if name != V4_PROCESS_NAME:
                continue
            cmdline = ' '.join(p.info.get('cmdline') or [])
            # Exclude helper processes (Go code excludes with "--")
            if '--' in cmdline:
                continue

            exe_path = p.info.get('exe') or ''
            full_ver = _get_file_version(exe_path) if exe_path else None

            # Infer data dir by scanning open files endswith V4_DB_REL
            data_dir: Optional[str] = None
            account_name: Optional[str] = None
            try:
                ofiles = p.open_files()
            except Exception:
                ofiles = []
            for of in ofiles:
                fp = of.path
                if fp.lower().endswith(V4_DB_REL.replace('\\', os.sep).replace('/', os.sep).lower()):
                    # Trim leading \\\\?\\ if present
                    if fp.startswith('\\\\?\\'):
                        fp = fp[4:]
                    parts = fp.split(os.sep)
                    if len(parts) >= 4:
                        # v4: DataDir = join(parts[:len-3]), AccountName = parts[len-4]
                        data_dir = os.sep.join(parts[:len(parts)-3])
                        account_name = parts[len(parts)-4]
                        break

            status = 'online' if data_dir else 'offline'
            results.append(WeChatProcess(pid=p.info['pid'], exe_path=exe_path, version=4, status=status, data_dir=data_dir, account_name=account_name, full_version=full_ver))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


# macOS implementation (filter to v4)
def _find_macos_v4() -> List[WeChatProcess]:
    results: List[WeChatProcess] = []
    for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            name = p.info.get('name') or ''
            if name not in (MAC_PROCESS_NAME_OFFICIAL, MAC_PROCESS_NAME_BETA):
                continue
            cmdline = ' '.join(p.info.get('cmdline') or [])
            if '--' in cmdline:
                continue
            exe_path = p.info.get('exe') or ''
            if not exe_path:
                try:
                    exe_path = p.exe()
                except Exception:
                    exe_path = ''

            ver_major, full_ver = _plist_version_from_exe(exe_path) if exe_path else (None, None)

            # Use lsof to find open files; prefer v4 path
            data_dir: Optional[str] = None
            account_name: Optional[str] = None
            files = _lsof_open_files(int(p.info['pid']))

            # Try detect v4 by open file path regardless of version parsing
            for fp in files:
                if MAC_V4_DB_REL in fp:
                    parts = fp.split('/')  # macOS uses '/'
                    if len(parts) >= 4:
                        data_dir = '/'.join(parts[:len(parts)-3])
                        account_name = parts[len(parts)-4]
                    break

            # Only include v4 processes
            is_v4 = (ver_major == 4) or (data_dir is not None)
            if not is_v4:
                continue

            status = 'online' if data_dir else 'offline'
            # If version not determined, set to 4 by detection
            version = 4
            results.append(WeChatProcess(pid=p.info['pid'], exe_path=exe_path, version=version, status=status, data_dir=data_dir, account_name=account_name, full_version=full_ver))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def find_wechat_v4_processes() -> List[WeChatProcess]:
    sysname = platform.system()
    if sysname == 'Windows':
        return _find_windows_v4()
    if sysname == 'Darwin':
        return _find_macos_v4()
    # Other OS not supported; return empty
    return []
