#!/usr/bin/env python3
"""
快速使用指南

本文件提供了微信 v4 消息解析模块的快速使用方法
"""

import os
import sys

def print_banner():
    """打印欢迎信息"""
    print("🚀 微信 v4 消息解析模块")
    print("=" * 50)
    print("📦 将 Go 版本的 PackedInfoData 解析逻辑转换为 Python")
    print("")

def check_dependencies():
    """检查依赖安装情况"""
    print("🔍 检查依赖安装情况:")
    
    # 检查 protobuf
    try:
        import google.protobuf
        print("  ✅ protobuf: 已安装")
    except ImportError:
        print("  ❌ protobuf: 未安装")
        print("     安装命令: pip install protobuf")
    
    # 检查 zstandard
    try:
        import zstandard
        print("  ✅ zstandard: 已安装")
    except ImportError:
        print("  ⚠️  zstandard: 未安装 (可选)")
        print("     安装命令: pip install zstandard")
    
    # 检查 protobuf 编译文件
    if os.path.exists("packedinfo_pb2.py"):
        print("  ✅ protobuf 编译文件: 已生成")
    else:
        print("  ❌ protobuf 编译文件: 未生成")
        print("     生成命令: python generate_proto.py")
    
    print("")

def show_installation_steps():
    """显示安装步骤"""
    print("📋 安装步骤:")
    print("1. 安装依赖包:")
    print("   pip install -r requirements_v4.txt")
    print("")
    print("2. 生成 protobuf 代码:")
    print("   python generate_proto.py")
    print("")
    print("3. 运行测试:")
    print("   python test_example.py")
    print("")

def show_usage_example():
    """显示使用示例"""
    print("💡 使用示例:")
    print("""
# 基本导入
from message_parser import MessageV4, wrap_message_v4

# 创建消息对象 (通常从数据库获取)
msg_v4 = MessageV4()
msg_v4.local_type = 3  # 图片消息
msg_v4.user_name = "sender"
msg_v4.create_time = 1640995200
msg_v4.message_content = b'<msg><img md5="abc123"/></msg>'
msg_v4.packed_info_data = b"..."  # 从数据库获取

# 转换消息
talker = "friend@example.com"
message = wrap_message_v4(msg_v4, talker)

# 查看结果
print(f"类型: {message.type}")
print(f"内容: {message.contents}")
""")

def show_file_structure():
    """显示文件结构"""
    print("📁 文件结构:")
    print("""
py/v4/
├── __init__.py              # 包初始化
├── message_parser.py        # 核心解析模块 ⭐
├── packedinfo.proto         # protobuf 定义
├── generate_proto.py        # protobuf 编译脚本
├── requirements_v4.txt      # 依赖包列表
├── test_example.py          # 测试示例
├── quick_start.py          # 快速开始指南 (本文件)
└── README.md               # 详细文档
""")

def show_key_features():
    """显示核心功能"""
    print("⭐ 核心功能:")
    print("  📷 图片消息解析 (Type=3)")
    print("  📹 视频消息解析 (Type=43)")
    print("  🗜️  zstd 消息解压")
    print("  🔗 媒体文件路径生成")
    print("  🔄 完整消息格式转换")
    print("")

def main():
    """主函数"""
    print_banner()
    check_dependencies()
    show_installation_steps()
    show_key_features()
    show_usage_example()
    show_file_structure()
    
    print("📚 更多信息:")
    print("  - 查看 README.md 获取详细文档")
    print("  - 运行 test_example.py 查看完整示例")
    print("  - 参考原 Go 代码: internal/model/message_v4.go")
    print("")
    print("🎯 核心对应关系:")
    print("  Go: MessageV4.Wrap()     → Python: wrap_message_v4()")
    print("  Go: ParsePackedInfo()    → Python: parse_packed_info()")
    print("  Go: zstd.Decompress()    → Python: decompress_message_content()")

if __name__ == "__main__":
    main()
