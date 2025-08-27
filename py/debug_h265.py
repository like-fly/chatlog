#!/usr/bin/env python3
"""
Debug script to understand why dat files are being converted to h265
"""

import os
import sys
import struct
import traceback
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent))

from dat2img.dat2img import dat2image
from dat2img.wxgf import wxam2pic, _find_partitions, convert2jpg

def debug_dat_file(dat_path):
    """Debug a single dat file to understand the conversion process"""
    print(f"\n=== Debugging {dat_path} ===")
    
    try:
        with open(dat_path, 'rb') as f:
            data = f.read()
        
        print(f"File size: {len(data)} bytes")
        print(f"Header: {data[:20].hex()}")
        
        # Manually do the dat2image process with debug info
        from dat2img.dat2img import V4_FORMATS, dat2image_v4, FORMATS, WXGF
        
        # Check which v4 format this is
        v4_format = None
        for f in V4_FORMATS:
            if data.startswith(f.Header):
                v4_format = f
                break
        
        if not v4_format:
            print("Not a recognized V4 format")
            return None, None
            
        print(f"V4 format detected: {v4_format.Header.hex()}")
        print(f"AES key: {v4_format.AesKey.hex() if v4_format.AesKey else 'None'}")
        
        # Try manual decryption to see what we get
        try:
            from dat2img.dat2img import decrypt_aes_ecb, v4_xor_key
            
            payload = data[len(v4_format.Header):]
            print(f"Payload size: {len(payload)} bytes")
            
            if len(payload) < 4:
                print("Payload too short")
                return None, None
                
            aes_len = struct.unpack('<I', payload[:4])[0]
            print(f"AES length: {aes_len}")
            
            if aes_len > len(payload) - 4:
                print("Invalid AES length")
                return None, None
                
            aes_len0 = (aes_len + 15) & ~15  # Round up to 16
            
            xor_len = len(payload) - 4 - aes_len0
            print(f"XOR length: {xor_len}")
            
            # Decrypt AES part
            if aes_len > 0 and v4_format.AesKey:
                aes_data = payload[4:4+aes_len0]
                dec = decrypt_aes_ecb(aes_data, v4_format.AesKey)[:aes_len]
                print(f"Decrypted AES data: {dec[:20].hex()}...")
            else:
                dec = b""
                
            # Build result
            result = bytearray()
            result += dec
            mid_start = aes_len0 + 4
            mid_end = len(payload)
            if xor_len > 0:
                mid_end = len(payload) - xor_len
                
            if mid_start < mid_end:
                result += payload[mid_start:mid_end]
                
            if xor_len > 0 and mid_end < len(payload):
                tail = payload[mid_end:]
                result += bytes([b ^ v4_xor_key for b in tail])
                
            print(f"Decrypted result size: {len(result)} bytes")
            print(f"Decrypted header: {result[:20].hex()}")
            
            # Check what format it is
            head = bytes(result[:4])
            if head.startswith(WXGF.Header):
                print("Detected WXGF format after decryption")
                from dat2img.wxgf import wxam2pic
                return wxam2pic(bytes(result))
            else:
                print("Checking other formats...")
                for f in FORMATS:
                    if result.startswith(f.Header):
                        print(f"Detected {f.Ext} format after decryption")
                        return bytes(result), f.Ext
                        
                print(f"Unknown format - first 32 bytes: {result[:32].hex()}")
                # Save the decrypted data for inspection
                with open("debug_decrypted.bin", 'wb') as f:
                    f.write(result)
                print("Saved decrypted data to debug_decrypted.bin")
                return None, None
                
        except Exception as e:
            print(f"Manual decryption failed: {e}")
            traceback.print_exc()
            return None, None
            
    except Exception as e:
        print(f"Failed to read file: {e}")
        return None, None

def main():
    # Test the specific file provided by user
    dat_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    if not os.path.exists(dat_file):
        print(f"File {dat_file} not found")
        return
        
    print(f"Analyzing specific file: {dat_file}")
    
    result_data, ext = debug_dat_file(dat_file)
    
    if result_data and ext:
        output_file = f"debug_output.{ext}"
        with open(output_file, 'wb') as f:
            f.write(result_data)
        print(f"\nSaved result to {output_file}")
        
        if ext == 'h265':
            print("\n=== H265 Analysis ===")
            print("File was converted to h265 instead of jpg/gif/mp4")
            print("This usually happens when:")
            print("1. FFmpeg cannot convert the h265 stream to jpg")
            print("2. The h265 stream format is not supported by ffmpeg")
            print("3. The partition/decryption resulted in corrupted data")
    else:
        print("Failed to process the file")

if __name__ == "__main__":
    main()
