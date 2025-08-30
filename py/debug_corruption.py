#!/usr/bin/env python3
"""
Comprehensive test to identify the image corruption issue
"""

import os
import sys
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent))

from dat2img.converter import WeChatDatConverter
from dat2img import dat2image, set_aes_key, scan_and_set_xor_key

def test_multiple_files():
    """Test multiple files to identify patterns in corruption"""
    print("=== Testing Multiple Files for Corruption Issues ===")
    
    # Set up both implementations
    aes_key = "32666261386464653536643364353161"
    
    # Find some test files
    test_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img"
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        return
    
    # Get first few dat files
    dat_files = []
    for f in os.listdir(test_dir):
        if f.endswith('.dat') and not f.endswith('_t.dat'):
            dat_files.append(os.path.join(test_dir, f))
            if len(dat_files) >= 3:  # Test 3 files
                break
    
    if not dat_files:
        print("No dat files found")
        return
    
    # Set up non-OO implementation
    scan_and_set_xor_key(test_dir)
    set_aes_key(aes_key)
    from dat2img.dat2img import v4_xor_key
    
    # Set up OO implementation  
    converter = WeChatDatConverter(
        aes_key=aes_key,
        xor_key=v4_xor_key
    )
    
    print(f"Using XOR key: 0x{v4_xor_key:02x}")
    print(f"Testing {len(dat_files)} files...\n")
    
    for i, dat_file in enumerate(dat_files):
        print(f"--- File {i+1}: {os.path.basename(dat_file)} ---")
        
        with open(dat_file, 'rb') as f:
            data = f.read()
        
        print(f"Size: {len(data)} bytes")
        
        # Test non-OO
        try:
            old_result, old_ext = dat2image(data)
            old_output = dat_file.replace('.dat', f'_test{i+1}_old.{old_ext}')
            with open(old_output, 'wb') as f:
                f.write(old_result)
            print(f"Non-OO: {len(old_result)} bytes -> {old_ext}")
        except Exception as e:
            print(f"Non-OO failed: {e}")
            continue
        
        # Test OO
        try:
            new_result, new_ext = converter.convert(data)
            new_output = dat_file.replace('.dat', f'_test{i+1}_new.{new_ext}')
            with open(new_output, 'wb') as f:
                f.write(new_result)
            print(f"OO: {len(new_result)} bytes -> {new_ext}")
        except Exception as e:
            print(f"OO failed: {e}")
            continue
        
        # Compare
        if len(old_result) == len(new_result) and old_result == new_result:
            print("✓ Results identical")
        else:
            print("✗ Results differ!")
            if len(old_result) != len(new_result):
                print(f"  Size: old={len(old_result)}, new={len(new_result)}")
            else:
                # Find differences
                diff_count = sum(1 for a, b in zip(old_result, new_result) if a != b)
                print(f"  {diff_count} bytes differ out of {len(old_result)}")
        
        print()


def test_specific_issue():
    """Test for specific known issues"""
    print("=== Testing for Specific Issues ===")
    
    # Test file that user mentioned has problems
    test_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    # Set up
    aes_key = "32666261386464653536643364353161"
    scan_and_set_xor_key(os.path.dirname(test_file))
    set_aes_key(aes_key)
    from dat2img.dat2img import v4_xor_key
    
    converter = WeChatDatConverter(aes_key=aes_key, xor_key=v4_xor_key)
    
    with open(test_file, 'rb') as f:
        data = f.read()
    
    print(f"Testing: {os.path.basename(test_file)}")
    print(f"Size: {len(data)} bytes")
    
    # Convert with both methods
    old_result, old_ext = dat2image(data)
    new_result, new_ext = converter.convert(data)
    
    # Check if they're really identical
    identical = old_result == new_result
    print(f"Results identical: {identical}")
    
    if identical:
        print("The issue might not be in the conversion logic itself.")
        print("Possible causes:")
        print("1. Different XOR key being used in your actual usage")
        print("2. File corruption during save/read")
        print("3. Different parameters in actual batch processing")
        print("4. Issue with file path handling in batch mode")
    else:
        print("Found difference in conversion results!")
        # Detailed analysis
        print(f"Old: {len(old_result)} bytes, ext: {old_ext}")
        print(f"New: {len(new_result)} bytes, ext: {new_ext}")
        
        if len(old_result) == len(new_result):
            # Find first difference
            for i, (a, b) in enumerate(zip(old_result, new_result)):
                if a != b:
                    print(f"First difference at byte {i}: 0x{a:02x} vs 0x{b:02x}")
                    break
    
    # Save both for manual inspection
    old_output = test_file.replace('.dat', '_compare_old.' + old_ext)
    new_output = test_file.replace('.dat', '_compare_new.' + new_ext)
    
    with open(old_output, 'wb') as f:
        f.write(old_result)
    with open(new_output, 'wb') as f:
        f.write(new_result)
    
    print(f"Saved comparison files:")
    print(f"  Old: {old_output}")
    print(f"  New: {new_output}")


def test_batch_mode_issue():
    """Test if the issue is specific to batch mode"""
    print("\n=== Testing Batch Mode vs Single File ===")
    
    test_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img"
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        return
    
    # Get one test file
    dat_files = [f for f in os.listdir(test_dir) if f.endswith('.dat') and not f.endswith('_t.dat')]
    if not dat_files:
        print("No dat files found")
        return
    
    test_file = os.path.join(test_dir, dat_files[0])
    
    # Setup
    aes_key = "32666261386464653536643364353161"
    scan_and_set_xor_key(test_dir)
    from dat2img.dat2img import v4_xor_key
    
    converter = WeChatDatConverter(aes_key=aes_key, xor_key=v4_xor_key)
    
    print(f"Testing file: {os.path.basename(test_file)}")
    
    # Method 1: Single file conversion
    output1 = converter.convert_file(test_file, test_file.replace('.dat', '_single.jpg'))
    print(f"Single file mode: {output1}")
    
    # Method 2: Batch conversion (single file)
    output_dir = r"D:\test_batch_single"
    os.makedirs(output_dir, exist_ok=True)
    
    results = converter.batch_convert(os.path.dirname(test_file), output_dir, preserve_structure=False)
    
    # Find our test file in results
    test_result = None
    for inp, out, success in results:
        if os.path.basename(inp) == os.path.basename(test_file):
            test_result = out
            break
    
    if test_result:
        print(f"Batch mode: {test_result}")
        
        # Compare the two files
        if os.path.exists(output1) and os.path.exists(test_result):
            with open(output1, 'rb') as f:
                single_data = f.read()
            with open(test_result, 'rb') as f:
                batch_data = f.read()
            
            if single_data == batch_data:
                print("✓ Single and batch modes produce identical results")
            else:
                print("✗ Single and batch modes produce different results!")
                print(f"  Single: {len(single_data)} bytes")
                print(f"  Batch: {len(batch_data)} bytes")
    else:
        print("Test file not found in batch results")


def main():
    """Run all tests"""
    test_specific_issue()
    test_multiple_files() 
    test_batch_mode_issue()


if __name__ == "__main__":
    main()
