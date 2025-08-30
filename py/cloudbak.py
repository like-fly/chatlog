import os
import time
from wechat_v4.extractor import extract_keys
from dat2img import dat2image, set_aes_key, scan_and_set_xor_key
from wechat_v4.process_detector import find_wechat_v4_processes
if __name__ == "__main__":
    print("Wechat v4 Key Extractor")
    print("=======================")
    print("This tool extracts encryption keys from a running WeChat v4 process. Please ensure WeChat v4 is running.")
    print("Limit Windows version: 4.0.3.36")
    print("Limit macOS version: 4.0.3.80")
    print("Ready to extract keys...")
    procs = find_wechat_v4_processes()
    if not procs:
        print("No WeChat v4 process found.")
        input("Press Enter to exit...")
        exit(0)
    # Use the first online process with data_dir
    proc = next((p for p in procs if p.status == 'online' and p.data_dir), procs[0])
    if not proc:
        print("No WeChat v4 process found.")
        print(f"Processes found: {len(procs)}")
        input("Press Enter to exit...")
        exit(0)
    start = time.perf_counter()
    data_key, img_key = extract_keys(proc)
    elapsed = time.perf_counter() - start
    print(f"extract_keys 耗时: {elapsed:.2f}s")
    print("Data Key:", data_key)
    print("Image Key:", img_key)
    if proc.data_dir:
        xor_key = scan_and_set_xor_key(proc.data_dir)
        print("XOR Key:", xor_key)
    input("Press Enter to exit...")