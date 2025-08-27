#!/usr/bin/env python3
"""
Test WXGF processing specifically
"""

import sys
sys.path.insert(0, '.')

from dat2img.dat2img import dat2image, set_aes_key
from dat2img.wxgf import wxam2pic, _find_partitions, convert2jpg

def test_wxgf_processing():
    # Set the correct AES key
    set_aes_key("32666261386464653536643364353161")
    
    # Read and process the dat file
    dat_file = r"D:\微信文件\xwechat_files\wxid_b125nd5rc59r12_6675\msg\attach\02a063747f7d52766a3b2da3e6b5f22f\2025-08\Img\fc1953520ab6c151a1bd09d5c251e7d4.dat"
    
    with open(dat_file, 'rb') as f:
        data = f.read()
    
    print("=== Manual DAT Decryption ===")
    # Manually decrypt to get the raw WXGF data
    from dat2img.dat2img import V4_FORMATS, decrypt_aes_ecb, v4_xor_key
    import struct
    
    # Find format
    v4_format = None
    for fmt in V4_FORMATS:
        if data.startswith(fmt.Header):
            v4_format = fmt
            break
    
    if not v4_format:
        print("No V4 format found")
        return
    
    # Decrypt manually
    aes_len = struct.unpack_from('<I', data, 6)[0]
    xor_len = struct.unpack_from('<I', data, 10)[0]
    payload = data[15:]
    aes_len0 = (aes_len // 16) * 16 + 16
    aes_len0 = min(aes_len0, len(payload))

    dec = decrypt_aes_ecb(payload[:aes_len0], v4_format.AesKey or b"")
    result = bytearray()
    result += dec[:aes_len]
    mid_start = aes_len0
    mid_end = len(payload) - xor_len
    if mid_start < mid_end:
        result += payload[mid_start:mid_end]
    if xor_len > 0 and mid_end < len(payload):
        tail = payload[mid_end:]
        result += bytes([b ^ v4_xor_key for b in tail])

    result_data = bytes(result)
    print(f'Decrypted data size: {len(result_data)}')
    print(f'Decrypted header: {result_data[:20].hex()}')
    
    # Check if it's WXGF
    if not result_data.startswith(b'wxgf'):
        print("Not WXGF format after decryption")
        return
    
    print("WXGF format confirmed!")
    
    print(f'WXGF header: {result_data[:20].hex()}')
    
    print("\n=== WXGF Partition Analysis ===")
    try:
        parts = _find_partitions(result_data)
        print(f'Found {len(parts["parts"])} partitions:')
        for i, (offset, size, ratio) in enumerate(parts['parts']):
            print(f'  Partition {i}: offset={offset}, size={size}, ratio={ratio:.3f}')
        
        # Get largest partition
        max_idx = parts['max_index']
        offset, size, ratio = parts['parts'][max_idx]
        h265_data = result_data[offset:offset+size]
        
        print(f'\nUsing partition {max_idx} (largest)')
        print(f'H265 data size: {len(h265_data)}')
        print(f'H265 header: {h265_data[:20].hex()}')
        
        # Save h265 data for inspection
        with open('debug_h265_data.bin', 'wb') as f:
            f.write(h265_data)
        print('Saved H265 data to debug_h265_data.bin')
        
        print("\n=== FFmpeg Conversion Test ===")
        try:
            jpg_data = convert2jpg(h265_data)
            print(f'FFmpeg success: {len(jpg_data)} bytes JPG')
            
            # Save successful JPG
            with open('debug_success.jpg', 'wb') as f:
                f.write(jpg_data)
            print('Saved JPG to debug_success.jpg')
            
        except Exception as e:
            print(f'FFmpeg failed: {e}')
            
            # Try to run ffmpeg manually to see detailed error
            import subprocess
            print("\n=== Manual FFmpeg Test ===")
            try:
                cmd = ["ffmpeg", "-i", "-", "-vframes", "1", "-c:v", "mjpeg", "-q:v", "4", "-f", "image2", "-"]
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = p.communicate(input=h265_data)
                
                print(f"FFmpeg return code: {p.returncode}")
                print(f"FFmpeg stderr: {err[:500].decode('utf-8', errors='ignore')}")
                
                if p.returncode == 0 and out:
                    print(f"Manual FFmpeg success: {len(out)} bytes")
                    with open('debug_manual_success.jpg', 'wb') as f:
                        f.write(out)
                else:
                    print("Manual FFmpeg also failed")
                    
            except Exception as e2:
                print(f"Manual FFmpeg error: {e2}")
            
    except Exception as e:
        print(f'Partition error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_wxgf_processing()
