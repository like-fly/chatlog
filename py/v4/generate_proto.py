#!/usr/bin/env python3
"""
生成 protobuf Python 代码的脚本
需要先安装 protobuf 编译器: pip install protobuf
"""

import subprocess
import sys
import os

def generate_protobuf():
    """生成 protobuf Python 代码"""
    try:
        # 编译 protobuf 文件
        result = subprocess.run([
            'protoc', 
            '--python_out=.', 
            'packedinfo.proto'
        ], check=True, capture_output=True, text=True)
        
        print("✅ protobuf 编译成功!")
        print("生成文件: packedinfo_pb2.py")
        
    except subprocess.CalledProcessError as e:
        print("❌ protobuf 编译失败:")
        print(f"错误: {e.stderr}")
        print("\n请确保已安装 protobuf 编译器:")
        print("pip install protobuf")
        print("或者下载官方编译器: https://github.com/protocolbuffers/protobuf/releases")
        
    except FileNotFoundError:
        print("❌ 未找到 protoc 命令")
        print("请安装 protobuf 编译器:")
        print("pip install protobuf")

if __name__ == "__main__":
    # 检查当前目录是否有 .proto 文件
    if not os.path.exists("packedinfo.proto"):
        print("❌ 未找到 packedinfo.proto 文件")
        sys.exit(1)
    
    generate_protobuf()
