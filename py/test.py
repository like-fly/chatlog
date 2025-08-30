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

    # data_key = '1e3c9e29a3b74c13a86f9a9f2ec5cd43e0d4f5b533614694a29a11236228414a'
    # img_key = '32666261386464653536643364353161'
    # set_aes_key(img_key)
    # data_dir = "D:\\微信文件\\xwechat_files\\wxid_b125nd5rc59r12_6675\\msg\\attach\\0dbb325accaea41b01220766aecfcfc3\\2025-07\\Img\\65d2103c900ef6c6d01c4c6202e9886e.dat"
    # scan_and_set_xor_key(data_dir)
    # target_dir = "D:\\cracked2"
    # with open(dat_path, 'rb') as f:
    #     data = f.read()
    # img_data, ext = dat2image(data)

        
        # # 递归扫描 data_dir 目录，将所有 .dat 文件转换为图片并保存到 target_dir 目录，保留原始目录结构
        # for root, _, files in os.walk(data_dir):
        #     for file in files:
        #         if file.endswith('.dat'):
        #             dat_path = os.path.join(root, file)
        #             try:
        #                 with open(dat_path, 'rb') as f:
        #                     data = f.read()
        #                 img_data, ext = dat2image(data)
        #                 target_path = os.path.join(target_dir, os.path.relpath(root, data_dir), file.replace('.dat', '.' + ext))
        #                 os.makedirs(os.path.dirname(target_path), exist_ok=True)
        #                 with open(target_path, 'wb') as img_file:
        #                     img_file.write(img_data)
                        
        #                 if ext == 'h265':
        #                     print(f"Converted {dat_path} to {target_path}")
        #             except Exception as e:
        #                 print(f"Failed to convert {dat_path}: {e}")
