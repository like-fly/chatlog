#!/usr/bin/env python3
"""
Object-oriented WeChat dat file converter
Optimized version of dat2img with cleaner API and better organization
"""

import os
import struct
import subprocess
from typing import Tuple, Optional, List, Union
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError as e:
    raise RuntimeError("pycryptodome is required. Please install with: pip install pycryptodome") from e


class ImageFormat:
    """Represents an image format with its header and extension"""
    
    def __init__(self, header: bytes, ext: str, aes_key: Optional[bytes] = None):
        self.header = header
        self.ext = ext
        self.aes_key = aes_key

    def __repr__(self):
        return f"ImageFormat({self.ext}, header={self.header.hex()[:8]}...)"


class WeChatDatConverter:
    """
    WeChat dat file converter with object-oriented design
    
    Usage:
        converter = WeChatDatConverter(
            aes_key="32666261386464653536643364353161",
            xor_key=0x37
        )
        image_data, extension = converter.convert(dat_file_data)
    """
    
    # Standard image formats
    FORMATS = [
        ImageFormat(b"\xFF\xD8\xFF", "jpg"),
        ImageFormat(b"\x89PNG", "png"),
        ImageFormat(b"GIF8", "gif"),
        ImageFormat(b"II*\x00", "tiff"),
        ImageFormat(b"BM", "bmp"),
        ImageFormat(b"wxgf", "wxgf"),
    ]
    
    # WeChat V4 formats
    V4_FORMATS = [
        ImageFormat(b"\x07\x08\x56\x31", "dat", b"cfcd208495d565ef"),
        ImageFormat(b"\x07\x08\x56\x32", "dat", b"0000000000000000"),
    ]
    
    # WXGF specific constants
    WXGF_HEADER = b"wxgf"
    MIN_RATIO = 0.6
    
    def __init__(self, aes_key: Optional[str] = None, xor_key: int = 0x37, ffmpeg_path: Optional[str] = None):
        """
        Initialize the converter
        
        Args:
            aes_key: Hex string of AES key for V4 format2 (32 hex chars = 16 bytes)
            xor_key: XOR key for tail data (default: 0x37)
            ffmpeg_path: Path to ffmpeg executable (auto-detected if None)
        """
        self.xor_key = xor_key
        
        # Set up V4 format with custom AES key
        self.v4_formats = [fmt for fmt in self.V4_FORMATS]
        if aes_key:
            try:
                aes_bytes = bytes.fromhex(aes_key)
                # Update V4_FORMAT2 with custom AES key
                self.v4_formats[1] = ImageFormat(
                    self.V4_FORMATS[1].header,
                    self.V4_FORMATS[1].ext,
                    aes_bytes
                )
            except ValueError:
                raise ValueError(f"Invalid AES key format: {aes_key}")
        
        # Set up FFmpeg
        self.ffmpeg_path = self._find_ffmpeg(ffmpeg_path)
        
    def _find_ffmpeg(self, custom_path: Optional[str]) -> str:
        """Find FFmpeg executable"""
        if custom_path:
            if os.path.isfile(custom_path):
                return custom_path
            elif os.path.isdir(custom_path):
                ffmpeg_exe = os.path.join(custom_path, "ffmpeg.exe")
                if os.path.isfile(ffmpeg_exe):
                    return ffmpeg_exe
        
        # Check environment variable
        env_path = os.environ.get("FFMPEG_PATH")
        if env_path:
            if os.path.isfile(env_path):
                return env_path
            elif os.path.isdir(env_path):
                ffmpeg_exe = os.path.join(env_path, "ffmpeg.exe")
                if os.path.isfile(ffmpeg_exe):
                    return ffmpeg_exe
        
        # Default to system PATH
        return "ffmpeg"
    
    def _decrypt_aes_ecb(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data using AES ECB mode"""
        if len(data) % 16 != 0:
            raise ValueError("Data length must be multiple of 16")
        
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = bytearray(len(data))
        
        for i in range(0, len(data), 16):
            decrypted[i:i+16] = cipher.decrypt(data[i:i+16])
        
        # Remove PKCS#7 padding if valid
        if decrypted:
            pad = decrypted[-1]
            if 0 < pad <= 16 and all(b == pad for b in decrypted[-pad:]):
                return bytes(decrypted[:-pad])
        
        return bytes(decrypted)
    
    def _convert_v4_format(self, data: bytes, aes_key: bytes) -> Tuple[bytes, str]:
        """Convert WeChat V4 format dat file"""
        if len(data) < 15:
            raise ValueError("Data too short for V4 format")
        
        # Parse V4 header
        aes_len = struct.unpack_from('<I', data, 6)[0]
        xor_len = struct.unpack_from('<I', data, 10)[0]
        payload = data[15:]
        
        # Calculate AES block size (round up to 16)
        aes_len0 = (aes_len // 16) * 16 + 16
        aes_len0 = min(aes_len0, len(payload))
        
        # Decrypt AES portion
        if aes_len > 0 and aes_key:
            dec = self._decrypt_aes_ecb(payload[:aes_len0], aes_key)
            aes_data = dec[:aes_len]
        else:
            aes_data = b""
        
        # Build result
        result = bytearray(aes_data)
        
        # Add middle portion (unencrypted)
        mid_start = aes_len0
        mid_end = len(payload) - xor_len
        if mid_start < mid_end:
            result += payload[mid_start:mid_end]
        
        # Add XOR portion
        if xor_len > 0 and mid_end < len(payload):
            tail = payload[mid_end:]
            result += bytes([b ^ self.xor_key for b in tail])
        
        # Determine format
        result_bytes = bytes(result)
        head = result_bytes[:4]
        
        if head.startswith(self.WXGF_HEADER):
            return self._convert_wxgf(result_bytes)
        
        for fmt in self.FORMATS:
            if result_bytes.startswith(fmt.header):
                return result_bytes, fmt.ext
        
        raise ValueError("Unknown image type after decryption")
    
    def _convert_legacy_xor(self, data: bytes) -> Tuple[bytes, str]:
        """Convert legacy XOR format dat file"""
        if len(data) < 4:
            raise ValueError("Data too short")
        
        # Try to detect XOR key from known headers
        for fmt in self.FORMATS[:5]:  # Skip WXGF for legacy
            if len(data) >= len(fmt.header):
                xor_key = data[0] ^ fmt.header[0]
                
                # Verify XOR pattern
                if all((data[i] ^ fmt.header[i]) == xor_key for i in range(len(fmt.header))):
                    # Decrypt entire file
                    decrypted = bytes(b ^ xor_key for b in data)
                    
                    # Verify it's the expected format
                    if decrypted.startswith(fmt.header):
                        return decrypted, fmt.ext
        
        raise ValueError("Unknown legacy format")
    
    def _find_wxgf_partitions(self, data: bytes) -> dict:
        """Find HEVC partitions in WXGF data"""
        if len(data) < 5:
            raise ValueError("Invalid WXGF data")
        
        header_len = data[4]
        if header_len >= len(data):
            raise ValueError("Invalid WXGF header length")
        
        patterns = [b"\x00\x00\x00\x01", b"\x00\x00\x01"]
        
        for pattern in patterns:
            parts = []
            max_ratio = 0.0
            max_idx = -1
            offset = 0
            
            while True:
                if header_len + offset >= len(data):
                    break
                
                # Search in remaining data
                search_data = data[header_len + offset:]
                idx = search_data.find(pattern)
                if idx == -1:
                    break
                
                abs_idx = header_len + offset + idx
                
                if abs_idx < 4:
                    offset += idx + 1
                    continue
                
                # Extract 4-byte big-endian length before pattern
                length = int.from_bytes(data[abs_idx-4:abs_idx], 'big')
                
                if length <= 0 or abs_idx + length > len(data):
                    offset += idx + 1
                    continue
                
                ratio = float(length) / float(len(data))
                parts.append((abs_idx, length, ratio))
                
                if ratio > max_ratio:
                    max_ratio = ratio
                    max_idx = len(parts) - 1
                
                # Move to next potential partition
                offset += idx + length
            
            if parts:
                return {
                    'parts': parts,
                    'max_ratio': max_ratio,
                    'max_index': max_idx,
                }
        
        raise ValueError("No partition found in WXGF data")
    
    def _run_ffmpeg(self, cmd: List[str], input_bytes: bytes) -> bytes:
        """Run FFmpeg command with input data"""
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=input_bytes)
            
            if process.returncode != 0:
                error_msg = stderr[:200].decode(errors='ignore') if stderr else "Unknown error"
                raise RuntimeError(f"FFmpeg failed: {error_msg}")
            
            if not stdout:
                raise RuntimeError("FFmpeg output is empty")
            
            return stdout
            
        except FileNotFoundError:
            raise RuntimeError(f"FFmpeg not found at: {self.ffmpeg_path}")
    
    def _convert_h265_to_jpg(self, h265_data: bytes) -> bytes:
        """Convert H265 data to JPG using FFmpeg"""
        cmd = [
            self.ffmpeg_path, "-i", "-",
            "-vframes", "1",
            "-c:v", "mjpeg",
            "-q:v", "4",
            "-f", "image2",
            "-"
        ]
        return self._run_ffmpeg(cmd, h265_data)
    
    def _convert_wxgf(self, data: bytes) -> Tuple[bytes, str]:
        """Convert WXGF format data"""
        if not data.startswith(self.WXGF_HEADER):
            raise ValueError("Invalid WXGF data")
        
        # Find partitions
        partitions = self._find_wxgf_partitions(data)
        
        # For anime-like content (multiple small partitions), we could implement
        # more complex logic here. For now, use the largest partition.
        parts = partitions['parts']
        max_idx = partitions['max_index']
        
        offset, size, ratio = parts[max_idx]
        h265_data = data[offset:offset+size]
        
        # Try to convert to JPG using FFmpeg
        try:
            jpg_data = self._convert_h265_to_jpg(h265_data)
            return jpg_data, 'jpg'
        except Exception:
            # Fallback: return raw H265 data
            return h265_data, 'h265'
    
    def convert(self, data: bytes) -> Tuple[bytes, str]:
        """
        Convert WeChat dat file data to image
        
        Args:
            data: Raw dat file content
            
        Returns:
            Tuple of (image_data, extension)
            
        Raises:
            ValueError: If data format is not supported
        """
        if len(data) < 4:
            raise ValueError("Data too short")
        
        # Try V4 formats first
        for fmt in self.v4_formats:
            if data.startswith(fmt.header):
                return self._convert_v4_format(data, fmt.aes_key or b"")
        
        # Try legacy XOR format
        return self._convert_legacy_xor(data)
    
    def convert_file(self, input_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> str:
        """
        Convert a dat file to image file
        
        Args:
            input_path: Path to input dat file
            output_path: Path to output image file (auto-generated if None)
            
        Returns:
            Path to output file
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Read input file
        with open(input_path, 'rb') as f:
            data = f.read()
        
        # Convert
        img_data, ext = self.convert(data)
        
        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix(f'.{ext}')
        else:
            output_path = Path(output_path)
        
        # Write output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(img_data)
        
        return str(output_path)
    
    def batch_convert(self, input_dir: Union[str, Path], output_dir: Union[str, Path], 
                     preserve_structure: bool = True) -> List[Tuple[str, str, bool]]:
        """
        Batch convert all dat files in a directory
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path
            preserve_structure: Whether to preserve directory structure
            
        Returns:
            List of (input_path, output_path, success) tuples
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        results = []
        
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        
        # Find all dat files
        dat_files = list(input_dir.rglob('*.dat'))
        
        for dat_file in dat_files:
            try:
                # Read and convert
                with open(dat_file, 'rb') as f:
                    data = f.read()
                
                img_data, ext = self.convert(data)
                
                # Determine output path
                if preserve_structure:
                    rel_path = dat_file.relative_to(input_dir)
                    output_path = output_dir / rel_path.with_suffix(f'.{ext}')
                else:
                    output_path = output_dir / f"{dat_file.stem}.{ext}"
                
                # Write output
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(img_data)
                
                results.append((str(dat_file), str(output_path), True))
                
            except Exception as e:
                results.append((str(dat_file), "", False))
                print(f"Failed to convert {dat_file}: {e}")
        
        return results
    
    @staticmethod
    def scan_xor_key(data_dir: Union[str, Path]) -> int:
        """
        Scan directory to find XOR key from thumbnail files
        
        Args:
            data_dir: Directory to scan for _t.dat files
            
        Returns:
            Detected XOR key (default: 0x37)
        """
        data_dir = Path(data_dir)
        
        for dat_file in data_dir.rglob('*_t.dat'):
            try:
                with open(dat_file, 'rb') as f:
                    data = f.read()
                
                # Check if it's a V4 format
                if len(data) < 17:
                    continue
                
                v4_headers = [b"\x07\x08\x56\x31", b"\x07\x08\x56\x32"]
                if not any(data.startswith(h) for h in v4_headers):
                    continue
                
                # Parse XOR length
                xor_len = struct.unpack_from('<I', data, 10)[0]
                tail = data[15:]
                
                if xor_len == 0 or xor_len > len(tail):
                    continue
                
                # Extract XOR data
                xor_data = tail[-xor_len:]
                if len(xor_data) >= 2:
                    # JPG files typically end with 0xFFD9
                    jpg_tail = b"\xFF\xD9"
                    keys = bytes([
                        xor_data[-2] ^ jpg_tail[0],
                        xor_data[-1] ^ jpg_tail[1]
                    ])
                    
                    if keys[0] == keys[1]:
                        return keys[0]
                        
            except Exception:
                continue
        
        return 0x37  # Default XOR key


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python converter.py <dat_file> [output_file]")
        return
    
    # Example with hardcoded keys (replace with your actual keys)
    converter = WeChatDatConverter(
        aes_key="32666261386464653536643364353161",
        xor_key=0x37
    )
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result_path = converter.convert_file(input_file, output_file)
        print(f"Converted: {input_file} -> {result_path}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
