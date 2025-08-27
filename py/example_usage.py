#!/usr/bin/env python3
"""
Simple example of using the new WeChat dat converter
"""

from dat2img.converter import WeChatDatConverter

def main():
    # Example 1: Basic usage with known keys
    print("Example 1: Basic conversion")
    converter = WeChatDatConverter(
        aes_key="32666261386464653536643364353161",  # Your image key
        xor_key=0xaf  # Detected XOR key
    )
    
    # Convert a single file
    input_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    try:
        output_file = converter.convert_file(input_file)
        print(f"Converted: {output_file}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\nExample 2: Batch conversion")
    # Batch convert all files in a directory
    input_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach"
    output_dir = r"D:\cracked_batch"
    
    # Convert only first 10 files for demonstration
    try:
        results = converter.batch_convert(input_dir, output_dir)
        
        # Show summary
        success = sum(1 for _, _, ok in results if ok)
        total = len(results)
        print(f"Batch conversion: {success}/{total} files successful")
        
        # Show first few results
        for i, (inp, out, ok) in enumerate(results[:5]):
            status = "✓" if ok else "✗"
            print(f"  {status} {inp.split('\\')[-1]} -> {out.split('\\')[-1] if out else 'failed'}")
        
        if total > 5:
            print(f"  ... and {total-5} more files")
            
    except Exception as e:
        print(f"Batch conversion error: {e}")
    
    print("\nExample 3: Auto-detect XOR key")
    # Automatically detect XOR key from directory
    data_dir = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach"
    detected_xor = WeChatDatConverter.scan_xor_key(data_dir)
    print(f"Auto-detected XOR key: 0x{detected_xor:02x}")
    
    # Use the detected key
    auto_converter = WeChatDatConverter(
        aes_key="32666261386464653536643364353161",
        xor_key=detected_xor
    )
    print("Created converter with auto-detected XOR key")

if __name__ == "__main__":
    main()
