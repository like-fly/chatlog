"""
微信 v4 版本消息解析包

此包包含了将 Go 版本的 PackedInfoData 解析逻辑转换为 Python 的实现。

主要功能:
1. 解析微信 v4 版本的 packed_info_data 字段
2. 处理图片和视频消息的文件路径生成
3. 支持 zstd 压缩消息内容的解压

使用方法:
    from py.v4.message_parser import wrap_message_v4, MessageV4
    
    # 创建消息对象
    msg_v4 = MessageV4()
    # ... 设置消息数据 ...
    
    # 转换为通用格式
    message = wrap_message_v4(msg_v4, talker)

依赖包:
    - protobuf: protobuf 解析
    - zstandard: zstd 解压缩 (可选)

生成 protobuf 代码:
    python generate_proto.py
"""

__version__ = "1.0.0"
__author__ = "ChatLog Project"

# 导入主要类和函数
try:
    from .message_parser import (
        MessageV4,
        Message, 
        wrap_message_v4,
        parse_packed_info,
        get_media_file_paths,
        decompress_message_content
    )
    
    __all__ = [
        'MessageV4',
        'Message',
        'wrap_message_v4', 
        'parse_packed_info',
        'get_media_file_paths',
        'decompress_message_content'
    ]
    
except ImportError as e:
    print(f"警告: 导入模块失败: {e}")
    print("请确保安装了必要的依赖包")
    __all__ = []
