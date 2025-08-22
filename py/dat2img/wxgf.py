import io
import os
import subprocess
from typing import List, Tuple

# Minimal Python re-implementation of wxgf handling:
# - find hevc partitions
# - if multiple partitions and ratio small -> anime flow (2 tracks)
# - otherwise single track, attempt ffmpeg jpg extraction else return mp4 bytes

WXGF_HEADER = b"wxgf"
ENV_FFMPEG_PATH = "FFMPEG_PATH"
FFMpegPath = os.environ.get(ENV_FFMPEG_PATH, "ffmpeg")

MIN_RATIO = 0.6


def _find_partitions(data: bytes):
    if len(data) < 5:
        raise ValueError("invalid wxgf")
    header_len = data[4]
    if header_len >= len(data):
        raise ValueError("invalid wxgf header length")
    patterns = [b"\x00\x00\x00\x01", b"\x00\x00\x01"]
    parts = []
    max_ratio = 0.0
    max_idx = -1
    for pat in patterns:
        parts = []
        off = 0
        while header_len + off < len(data):
            idx = data.find(pat, header_len + off)
            if idx == -1:
                break
            abs_idx = idx
            if abs_idx < 4:
                off += (idx - off) + 1
                continue
            length = int.from_bytes(data[abs_idx-4:abs_idx], 'big')
            if length <= 0 or abs_idx + length > len(data):
                off += (idx - off) + 1
                continue
            ratio = float(length) / float(len(data))
            parts.append((abs_idx, length, ratio))
            if ratio > max_ratio:
                max_ratio = ratio
                max_idx = len(parts) - 1
            off = (idx - header_len) + length
        if parts:
            return {
                'parts': parts,
                'max_ratio': max_ratio,
                'max_index': max_idx,
            }
    raise ValueError("no partition found")


def _run_ffmpeg(cmd: list, input_bytes: bytes) -> bytes:
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=input_bytes)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err[:200].decode(errors='ignore')}")
    if not out:
        raise RuntimeError("ffmpeg output is empty")
    return out


def convert2jpg(h265_bytes: bytes) -> bytes:
    # ffmpeg -i - -vframes 1 -c:v mjpeg -q:v 4 -f image2 -
    cmd = [FFMpegPath, "-i", "-", "-vframes", "1", "-c:v", "mjpeg", "-q:v", "4", "-f", "image2", "-"]
    return _run_ffmpeg(cmd, h265_bytes)


def wxam2pic(data: bytes) -> Tuple[bytes, str]:
    if len(data) < 15 or not data.startswith(WXGF_HEADER):
        raise ValueError("invalid wxgf")
    parts = _find_partitions(data)
    # Anime-like (two interleaved tracks), we fallback to mp4 output using ffmpeg concat-like approach is complex;
    # here we return mp4 for simple single-track; for anime-like we try building mp4 via single track of largest part.
    offset, size, _ = parts['parts'][parts['max_index']]
    h265 = data[offset:offset+size]
    try:
        jpg = convert2jpg(h265)
        return jpg, 'jpg'
    except Exception:
        # fallback: return raw h265 packed into MP4 is non-trivial without mp4 muxer; return the raw bytes
        return h265, 'h265'
