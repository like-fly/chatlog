#!/usr/bin/env python3
"""
微信 v4 消息解析使用示例和测试

此文件演示如何使用 message_parser 模块解析微信 v4 版本的消息数据
"""

import sys
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any

# 添加当前目录到 Python 路径
sys.path.append('.')

try:
    from message_parser import (
        MessageV4, 
        Message, 
        wrap_message_v4,
        get_media_file_paths,
        decompress_message_content
    )
    print("✅ 成功导入 message_parser 模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保安装了依赖包: pip install -r requirements_v4.txt")
    sys.exit(1)


def create_test_image_message() -> MessageV4:
    """创建测试图片消息"""
    msg = MessageV4()
    msg.sort_seq = 1234567890123
    msg.server_id = 123456
    msg.local_type = 3  # 图片消息
    msg.user_name = "testuser"
    msg.create_time = int(time.time())
    msg.message_content = b'<msg><img md5="abc123def456" /></msg>'
    msg.status = 2
    
    # 注意: 这里应该是真实的 protobuf 数据
    # 实际使用时，packed_info_data 来自数据库查询结果
    msg.packed_info_data = b""  # 模拟数据
    
    return msg


def create_test_video_message() -> MessageV4:
    """创建测试视频消息"""
    msg = MessageV4()
    msg.sort_seq = 1234567890124
    msg.server_id = 123457
    msg.local_type = 43  # 视频消息
    msg.user_name = "testuser"
    msg.create_time = int(time.time())
    msg.message_content = b'<msg><videomsg md5="video123" /></msg>'
    msg.status = 2
    
    msg.packed_info_data = b""  # 模拟数据
    
    return msg


def create_test_text_message() -> MessageV4:
    """创建测试文本消息"""
    msg = MessageV4()
    msg.sort_seq = 1234567890125
    msg.server_id = 123458
    msg.local_type = 1  # 文本消息
    msg.user_name = "testuser"
    msg.create_time = int(time.time())
    msg.message_content = "这是一条测试文本消息".encode('utf-8')
    msg.status = 2
    
    msg.packed_info_data = b""
    
    return msg


def test_message_conversion():
    """测试消息转换功能"""
    print("\n🧪 开始测试消息转换功能")
    
    talker = "friend@wechat.com"
    
    # 测试图片消息
    print("\n📷 测试图片消息:")
    img_msg_v4 = create_test_image_message()
    img_message = wrap_message_v4(img_msg_v4, talker)
    
    print(f"  类型: {img_message.type}")
    print(f"  时间: {img_message.time}")
    print(f"  发送者: {img_message.sender}")
    print(f"  内容: {img_message.content}")
    print(f"  扩展信息: {img_message.contents}")
    
    # 测试视频消息
    print("\n📹 测试视频消息:")
    video_msg_v4 = create_test_video_message()
    video_message = wrap_message_v4(video_msg_v4, talker)
    
    print(f"  类型: {video_message.type}")
    print(f"  时间: {video_message.time}")
    print(f"  发送者: {video_message.sender}")
    print(f"  内容: {video_message.content}")
    print(f"  扩展信息: {video_message.contents}")
    
    # 测试文本消息
    print("\n💬 测试文本消息:")
    text_msg_v4 = create_test_text_message()
    text_message = wrap_message_v4(text_msg_v4, talker)
    
    print(f"  类型: {text_message.type}")
    print(f"  时间: {text_message.time}")
    print(f"  发送者: {text_message.sender}")
    print(f"  内容: {text_message.content}")


def test_media_paths():
    """测试媒体文件路径生成"""
    print("\n🔗 测试媒体文件路径生成")
    
    # 创建包含媒体信息的消息
    message = Message()
    message.type = 3  # 图片消息
    message.contents = {
        "imgfile": "msg/attach/abc123/2024-01/Img/def456.dat",
        "thumb": "msg/attach/abc123/2024-01/Img/def456_t.dat"
    }
    
    host = "localhost:8080"
    paths = get_media_file_paths(message, host)
    
    print(f"  图片路径: {paths}")


def test_zstd_decompression():
    """测试 zstd 解压功能"""
    print("\n🗜️  测试 zstd 解压功能")
    
    # 测试普通文本
    normal_text = "这是普通文本".encode('utf-8')
    result = decompress_message_content(normal_text)
    print(f"  普通文本: {result}")
    
    # 测试 zstd 压缩数据（模拟）
    try:
        import zstandard as zstd
        
        # 压缩测试数据
        original = "这是被压缩的消息内容"
        cctx = zstd.ZstdCompressor()
        compressed = cctx.compress(original.encode('utf-8'))
        
        # 解压
        decompressed = decompress_message_content(compressed)
        print(f"  压缩文本: {decompressed}")
        
    except ImportError:
        print("  ⚠️  zstandard 包未安装，跳过压缩测试")


def show_file_path_examples():
    """显示文件路径生成示例"""
    print("\n📁 文件路径生成示例")
    
    talker = "user123@chatroom"
    talker_md5 = hashlib.md5(talker.encode('utf-8')).hexdigest()
    current_time = datetime.now()
    time_format = current_time.strftime("%Y-%m")
    
    print(f"  聊天对象: {talker}")
    print(f"  MD5 哈希: {talker_md5}")
    print(f"  时间格式: {time_format}")
    
    # 图片文件路径示例
    img_md5 = "abcdef123456789"
    img_path = f"msg/attach/{talker_md5}/{time_format}/Img/{img_md5}.dat"
    thumb_path = f"msg/attach/{talker_md5}/{time_format}/Img/{img_md5}_t.dat"
    
    print(f"  图片路径: {img_path}")
    print(f"  缩略图路径: {thumb_path}")
    
    # 视频文件路径示例
    video_md5 = "xyz789abcdef123"
    video_path = f"msg/video/{time_format}/{video_md5}.mp4"
    video_thumb_path = f"msg/video/{time_format}/{video_md5}_thumb.jpg"
    
    print(f"  视频路径: {video_path}")
    print(f"  视频缩略图: {video_thumb_path}")


def main():
    """主函数"""
    print("🚀 微信 v4 消息解析模块测试")
    print("=" * 50)
    
    # 运行各项测试
    test_message_conversion()
    test_media_paths()
    test_zstd_decompression()
    show_file_path_examples()
    
    print("\n✅ 测试完成!")
    print("\n📝 使用说明:")
    print("1. 安装依赖: pip install -r requirements_v4.txt")
    print("2. 生成 protobuf: python generate_proto.py")
    print("3. 在实际项目中导入: from py.v4 import wrap_message_v4")


if __name__ == "__main__":
    main()
