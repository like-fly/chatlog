#!/usr/bin/env python3
"""
Debug script to compare Go and Python implementations and test different AES keys
"""

import os
import sys
import struct
import traceback
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent))

from dat2img.dat2img import dat2image, set_aes_key, V4_FORMATS, decrypt_aes_ecb, v4_xor_key, FORMATS, WXGF
from dat2img.wxgf import wxam2pic, _find_partitions, convert2jpg

def test_aes_key(data, test_key_hex, label):
    """Test a specific AES key with the dat file"""
    print(f"\n--- Testing {label} (key: {test_key_hex}) ---")
    
    try:
        # Set the test key
        set_aes_key(test_key_hex)
        
        # Try dat2image conversion
        result_data, ext = dat2image(data)
        print(f"Success! Extension: {ext}, Size: {len(result_data)} bytes")
        
        if ext == 'wxgf':
            print("WXGF format detected - analyzing partitions...")
            try:
                parts = _find_partitions(result_data)
                print(f"Found {len(parts['parts'])} partitions")
                
                # Try converting the largest partition
                max_idx = parts['max_index']
                offset, size, ratio = parts['parts'][max_idx]
                h265_data = result_data[offset:offset+size]
                
                print(f"Using partition {max_idx}: size={size}, ratio={ratio:.3f}")
                print(f"H265 header: {h265_data[:16].hex()}")
                
                # Try FFmpeg conversion
                try:
                    jpg_data = convert2jpg(h265_data)
                    print(f"FFmpeg conversion successful: {len(jpg_data)} bytes JPG")
                    return jpg_data, 'jpg'
                except Exception as e:
                    print(f"FFmpeg conversion failed: {e}")
                    return h265_data, 'h265'
                    
            except Exception as e:
                print(f"WXGF processing failed: {e}")
                return result_data, ext
        else:
            return result_data, ext
            
    except Exception as e:
        print(f"Failed with key {test_key_hex}: {e}")
        return None, None

def analyze_dat_structure(data):
    """Analyze the raw structure of a dat file"""
    print(f"\n=== DAT File Structure Analysis ===")
    print(f"File size: {len(data)} bytes")
    print(f"Full header (first 32 bytes): {data[:32].hex()}")
    
    # Check format headers
    for fmt in V4_FORMATS:
        if data.startswith(fmt.Header):
            print(f"Matches V4 format: {fmt.Header.hex()}")
            
            # Parse the structure manually
            if len(data) >= 15:
                header = data[:4]
                byte4 = data[4]  # Usually version or flags
                byte5 = data[5]  # Usually version or flags
                aes_len = struct.unpack('<I', data[6:10])[0]
                xor_len = struct.unpack('<I', data[10:14])[0]
                reserved = data[14]
                
                print(f"Header: {header.hex()}")
                print(f"Byte 4-5: {byte4:02x} {byte5:02x}")
                print(f"AES length: {aes_len}")
                print(f"XOR length: {xor_len}")
                print(f"Reserved byte: {reserved:02x}")
                print(f"Payload starts at offset 15, size: {len(data) - 15}")
                
                # Check if lengths make sense
                payload_size = len(data) - 15
                if aes_len + xor_len > payload_size:
                    print(f"WARNING: AES({aes_len}) + XOR({xor_len}) = {aes_len + xor_len} > payload({payload_size})")
                    print("This indicates the file structure may be corrupted or use a different format")
                else:
                    print("Length fields appear valid")
                    
                return fmt
    
    print("No matching V4 format found")
    return None

def manual_decrypt_with_key(data, key_hex):
    """Manually decrypt with detailed logging"""
    print(f"\n=== Manual Decryption with key {key_hex} ===")
    
    # Find matching format
    v4_format = None
    for fmt in V4_FORMATS:
        if data.startswith(fmt.Header):
            v4_format = fmt
            break
    
    if not v4_format:
        print("No V4 format match")
        return None
        
    # Parse structure
    aes_len = struct.unpack('<I', data[6:10])[0]
    xor_len = struct.unpack('<I', data[10:14])[0]
    payload = data[15:]
    
    print(f"AES length: {aes_len}")
    print(f"XOR length: {xor_len}")
    print(f"Payload size: {len(payload)}")
    
    # Calculate AES block size (rounded up to 16)
    aes_len0 = (aes_len // 16) * 16 + 16
    aes_len0 = min(aes_len0, len(payload))
    
    print(f"AES block size: {aes_len0}")
    
    # Decrypt AES part
    key_bytes = bytes.fromhex(key_hex)
    print(f"Using AES key: {key_bytes.hex()}")
    
    if aes_len0 > 0:
        aes_data = payload[:aes_len0]
        print(f"AES data (first 16 bytes): {aes_data[:16].hex()}")
        
        try:
            decrypted = decrypt_aes_ecb(aes_data, key_bytes)
            print(f"Decrypted (first 16 bytes): {decrypted[:16].hex()}")
            
            # Take only the actual AES length
            dec_actual = decrypted[:aes_len]
            print(f"Actual decrypted length: {len(dec_actual)}")
            
        except Exception as e:
            print(f"AES decryption failed: {e}")
            return None
    else:
        dec_actual = b""
    
    # Build result
    result = bytearray()
    result += dec_actual
    
    # Add middle part (between AES and XOR)
    mid_start = aes_len0
    mid_end = len(payload) - xor_len
    
    if mid_start < mid_end:
        mid_part = payload[mid_start:mid_end]
        result += mid_part
        print(f"Middle part: {len(mid_part)} bytes")
    
    # XOR part
    if xor_len > 0 and mid_end < len(payload):
        xor_part = payload[mid_end:]
        print(f"XOR part (before): {xor_part[:16].hex()}")
        xor_decrypted = bytes([b ^ v4_xor_key for b in xor_part])
        print(f"XOR part (after): {xor_decrypted[:16].hex()}")
        result += xor_decrypted
    
    print(f"Final result size: {len(result)}")
    print(f"Final result header: {result[:20].hex()}")
    
    # Check format
    if result.startswith(WXGF.Header):
        print("Result is WXGF format")
    else:
        for fmt in FORMATS:
            if result.startswith(fmt.Header):
                print(f"Result is {fmt.Ext} format")
                return result, fmt.Ext
        print("Unknown result format")
    
    return result, 'unknown'

def main():
    dat_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    if not os.path.exists(dat_file):
        print(f"File {dat_file} not found")
        return
    
    with open(dat_file, 'rb') as f:
        data = f.read()
    
    # 1. Analyze file structure
    fmt = analyze_dat_structure(data)
    
    # 2. Test different AES keys
    test_keys = [
        # Current key from test.py
        ("Current key", "32666261386464653536643364353161"),
        # Go default keys
        ("Go V4_FORMAT1", "cfcd208495d565ef"),
        ("Go V4_FORMAT2", "0000000000000000"),
        # Try converting current key to different formats
        ("Current as bytes", "3266626138646465"),  # First 8 bytes
        ("Current reversed", "61356433643564656464386162663233"),  # Reversed
    ]
    
    successful_conversions = []
    
    for label, key_hex in test_keys:
        result_data, ext = test_aes_key(data, key_hex, label)
        if result_data and ext != 'h265':
            successful_conversions.append((label, key_hex, ext, len(result_data)))
            
            # Save successful conversion
            output_file = f"debug_success_{label.replace(' ', '_')}.{ext}"
            with open(output_file, 'wb') as f:
                f.write(result_data)
            print(f"Saved successful conversion to {output_file}")
    
    print(f"\n=== Summary ===")
    if successful_conversions:
        print("Successful conversions:")
        for label, key, ext, size in successful_conversions:
            print(f"  {label}: {ext} ({size} bytes)")
    else:
        print("No successful conversions found")
        print("This suggests either:")
        print("1. The AES key is incorrect")
        print("2. The file format is different from expected")
        print("3. The file is corrupted")
        
        # Try manual decryption with current key for detailed analysis
        print("\n=== Attempting detailed manual decryption ===")
        manual_decrypt_with_key(data, "32666261386464653536643364353161")

if __name__ == "__main__":
    main()
