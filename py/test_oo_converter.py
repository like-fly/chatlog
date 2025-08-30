#!/usr/bin/env python3
"""
Test script for the new object-oriented WeChat dat converter
"""

import os
import sys
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent))

from dat2img.converter import WeChatDatConverter


def test_single_file():
    """Test converting a single file"""
    print("=== Testing Single File Conversion ===")
    
    # Initialize converter with keys
    converter = WeChatDatConverter(
        aes_key="32666261386464653536643364353161",
        xor_key=0xaf  # Use the correct detected XOR key
    )
    
    # Test file from user's example
    test_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    try:
        # Convert using the new API
        output_path = converter.convert_file(test_file)
        print(f"Successfully converted: {test_file}")
        print(f"Output: {output_path}")
        
        # Check if output file exists and get its size
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"Output size: {size} bytes")
            
            # Determine if it's a successful image conversion
            ext = output_path.split('.')[-1].lower()
            if ext in ['jpg', 'png', 'gif', 'bmp']:
                print("✓ Successfully converted to image format")
            elif ext == 'h265':
                print("⚠ Converted to h265 (FFmpeg conversion may have failed)")
            else:
                print(f"? Unknown output format: {ext}")
        
    except Exception as e:
        print(f"Conversion failed: {e}")


def test_batch_conversion():
    """Test batch conversion of multiple files"""
    print("\n=== Testing Batch Conversion ===")
    
    # Initialize converter
    converter = WeChatDatConverter(
        aes_key="32666261386464653536643364353161",
        xor_key=0xaf  # Use the correct detected XOR key
    )
    
    # Test directory (subset of user's directory)
    input_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img"
    output_dir = r"D:\cracked_oo_test"
    
    if not os.path.exists(input_dir):
        print(f"Test directory not found: {input_dir}")
        return
    
    try:
        # Convert first 5 files only for testing
        results = converter.batch_convert(input_dir, output_dir, preserve_structure=True)
        
        # Limit to first 5 for testing
        results = results[:5]
        
        print(f"Processed {len(results)} files:")
        
        success_count = 0
        h265_count = 0
        image_count = 0
        
        for input_path, output_path, success in results:
            if success:
                success_count += 1
                ext = output_path.split('.')[-1].lower()
                if ext in ['jpg', 'png', 'gif', 'bmp']:
                    image_count += 1
                    print(f"✓ {os.path.basename(input_path)} -> {ext}")
                elif ext == 'h265':
                    h265_count += 1
                    print(f"⚠ {os.path.basename(input_path)} -> h265")
                else:
                    print(f"? {os.path.basename(input_path)} -> {ext}")
            else:
                print(f"✗ {os.path.basename(input_path)} -> failed")
        
        print(f"\nSummary:")
        print(f"  Total processed: {len(results)}")
        print(f"  Successful: {success_count}")
        print(f"  Image formats: {image_count}")
        print(f"  H265 fallbacks: {h265_count}")
        print(f"  Failed: {len(results) - success_count}")
        
    except Exception as e:
        print(f"Batch conversion failed: {e}")


def test_xor_key_detection():
    """Test automatic XOR key detection"""
    print("\n=== Testing XOR Key Detection ===")
    
    test_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach"
    
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        return
    
    try:
        detected_key = WeChatDatConverter.scan_xor_key(test_dir)
        print(f"Detected XOR key: 0x{detected_key:02x}")
        
        if detected_key == 0x37:
            print("✓ Matches expected default key")
        else:
            print(f"ⓘ Different from default (0x37)")
        
    except Exception as e:
        print(f"XOR key detection failed: {e}")


def test_api_comparison():
    """Test the new API vs old API"""
    print("\n=== API Comparison ===")
    
    test_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    # Read test data
    with open(test_file, 'rb') as f:
        data = f.read()
    
    print("Old API usage:")
    try:
        from dat2img import dat2image, set_aes_key
        set_aes_key("32666261386464653536643364353161")
        old_result, old_ext = dat2image(data)
        print(f"  Result: {len(old_result)} bytes, extension: {old_ext}")
    except Exception as e:
        print(f"  Failed: {e}")
    
    print("\nNew API usage:")
    try:
        converter = WeChatDatConverter(
            aes_key="32666261386464653536643364353161",
            xor_key=0xaf  # Use the correct detected XOR key
        )
        new_result, new_ext = converter.convert(data)
        print(f"  Result: {len(new_result)} bytes, extension: {new_ext}")
    except Exception as e:
        print(f"  Failed: {e}")


def main():
    """Run all tests"""
    print("WeChat Dat Converter - Object-Oriented API Test")
    print("=" * 50)
    
    test_single_file()
    test_xor_key_detection() 
    test_api_comparison()
    test_batch_conversion()
    
    print("\n" + "=" * 50)
    print("Test completed!")


if __name__ == "__main__":
    main()
