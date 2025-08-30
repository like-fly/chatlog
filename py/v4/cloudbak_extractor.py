import os
import time
from wechat_v4.extractor import extract_keys
from dat2img import dat2image, set_aes_key, scan_and_set_xor_key
from wechat_v4.process_detector import find_wechat_v4_processes
if __name__ == "__main__":

    procs = find_wechat_v4_processes()
    if procs:
        proc = next((p for p in procs if p.status == 'online' and p.data_dir), procs[0])
        print(f"Found WeChat process: PID={proc.pid}, DataDir={proc.data_dir}, AccountName={proc.account_name}")
        print(f"Full Version: {proc.full_version}")

        # 提取耗时
        start = time.perf_counter()
        data_key, img_key = extract_keys()
        elapsed = time.perf_counter() - start
        print(f"extract_keys 耗时: {elapsed:.2f}s")
        print("Data Key:", data_key)
        print("Image Key:", img_key)
        if proc.data_dir:
            xor_key = scan_and_set_xor_key(proc.data_dir)
            print("XOR Key:", xor_key)