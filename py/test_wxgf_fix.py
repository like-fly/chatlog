#!/usr/bin/env python3

import os
from dat2img import dat2image

# Test one of the problematic files
test_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\238fccb1d118be2667d1dbac13c56d13.dat"

if os.path.exists(test_file):
    print(f"Testing file: {test_file}")
    try:
        with open(test_file, 'rb') as f:
            data = f.read()
        
        print(f"File size: {len(data)} bytes")
        print(f"First 20 bytes: {data[:20].hex()}")
        
        # Try to convert
        img_data, ext = dat2image(data)
        print(f"✅ Success! Converted to {ext}, output size: {len(img_data)} bytes")
        
        # Save test output
        output_file = f"test_output.{ext}"
        with open(output_file, 'wb') as f:
            f.write(img_data)
        print(f"Saved test output to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print(f"Test file not found: {test_file}")
