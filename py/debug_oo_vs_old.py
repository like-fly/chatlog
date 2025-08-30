#!/usr/bin/env python3
"""
Compare OO vs non-OO implementation for the specific dat file
"""

import os
import sys
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent))

from dat2img import dat2image, set_aes_key, scan_and_set_xor_key
from dat2img.converter import WeChatDatConverter

def compare_implementations():
    """Compare OO vs non-OO implementation for the same file"""
    
    # Test file path from user
    dat_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\0dbb325accaea41b01220766aecfcfc3\2025-07\Img\65d2103c900ef6c6d01c4c6202e9886e.dat"
    
    if not os.path.exists(dat_file):
        print(f"Test file not found: {dat_file}")
        return
    
    # Read the file once
    with open(dat_file, 'rb') as f:
        data = f.read()
    
    print(f"Testing file: {os.path.basename(dat_file)}")
    print(f"File size: {len(data)} bytes")
    print(f"File header: {data[:20].hex()}")
    
    # Keys
    aes_key = "32666261386464653536643364353161"
    
    # Detect XOR key from the data directory
    data_dir = os.path.dirname(dat_file)
    
    # Output directory
    output_dir = "d:/cracked2"
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*60)
    print("NON-OO IMPLEMENTATION")
    print("="*60)
    
    try:
        # Set up non-OO way
        set_aes_key(aes_key)
        detected_xor = scan_and_set_xor_key(data_dir)
        print(f"Detected XOR key: 0x{detected_xor:02x}")
        
        # Convert using non-OO
        old_result, old_ext = dat2image(data)
        print(f"Result: {len(old_result)} bytes, extension: {old_ext}")
        
        # Save non-OO result
        old_output = os.path.join(output_dir, f"non_oo_result.{old_ext}")
        with open(old_output, 'wb') as f:
            f.write(old_result)
        print(f"Saved to: {old_output}")
        
        # Show first few bytes of result
        print(f"Result header: {old_result[:20].hex()}")
        
    except Exception as e:
        print(f"Non-OO failed: {e}")
        import traceback
        traceback.print_exc()
        old_result = None
        old_ext = None
    
    print("\n" + "="*60)
    print("OO IMPLEMENTATION")
    print("="*60)
    
    try:
        # Detect XOR key using OO method
        oo_detected_xor = WeChatDatConverter.scan_xor_key(data_dir)
        print(f"Detected XOR key: 0x{oo_detected_xor:02x}")
        
        # Set up OO way
        converter = WeChatDatConverter(
            aes_key=aes_key,
            xor_key=oo_detected_xor
        )
        
        # Convert using OO
        new_result, new_ext = converter.convert(data)
        print(f"Result: {len(new_result)} bytes, extension: {new_ext}")
        
        # Save OO result
        new_output = os.path.join(output_dir, f"oo_result.{new_ext}")
        with open(new_output, 'wb') as f:
            f.write(new_result)
        print(f"Saved to: {new_output}")
        
        # Show first few bytes of result
        print(f"Result header: {new_result[:20].hex()}")
        
    except Exception as e:
        print(f"OO failed: {e}")
        import traceback
        traceback.print_exc()
        new_result = None
        new_ext = None
    
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    
    if old_result is not None and new_result is not None:
        if old_result == new_result:
            print("✓ Results are identical")
        else:
            print("✗ Results are different!")
            print(f"  Non-OO size: {len(old_result)} bytes")
            print(f"  OO size: {len(new_result)} bytes")
            
            # Compare first 100 bytes
            min_len = min(len(old_result), len(new_result))
            if min_len > 0:
                diff_found = False
                for i in range(min(100, min_len)):
                    if old_result[i] != new_result[i]:
                        print(f"  First difference at byte {i}: {old_result[i]:02x} vs {new_result[i]:02x}")
                        diff_found = True
                        break
                
                if not diff_found and len(old_result) != len(new_result):
                    print(f"  Same content but different lengths")
        
        if old_ext == new_ext:
            print(f"✓ Extensions match: {old_ext}")
        else:
            print(f"✗ Extensions differ: {old_ext} vs {new_ext}")
    
    elif old_result is None and new_result is None:
        print("✗ Both implementations failed")
    elif old_result is None:
        print("✗ Non-OO failed, OO succeeded")
    else:
        print("✗ OO failed, non-OO succeeded")
    
    print(f"\nOutput files saved in: {output_dir}")
    print("Please check the generated image files manually to see if they display correctly.")


if __name__ == "__main__":
    compare_implementations()