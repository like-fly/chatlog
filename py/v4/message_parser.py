"""
微信 v4 版本消息处理模块
将 Go 代码中的 PackedInfoData 解析逻辑转换为 Python 实现
"""

import hashlib
import os
import struct
import time
from datetime import datetime
from typing import Optional, Dict, Any, Union

# 可选依赖处理
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    print("警告: zstandard 未安装，将跳过 zstd 解压功能")

try:
    # 尝试导入生成的 protobuf 文件
    from . import packedinfo_pb2
    HAS_PROTOBUF = True
except ImportError:
    try:
        # 尝试直接导入
        import packedinfo_pb2
        HAS_PROTOBUF = True
    except ImportError:
        HAS_PROTOBUF = False
        print("警告: 未找到 protobuf 编译文件，请运行 'python generate_proto.py' 生成")
        
        # 提供简单的类定义作为后备
        class ImageHash:
            def __init__(self):
                self.md5 = ""
        
        class VideoHash:
            def __init__(self):
                self.md5 = ""
        
        class PackedInfo:
            def __init__(self):
                self.type = 0
                self.version = 0
                self.image = None
                self.video = None


class MessageV4:
    """微信 v4 版本消息结构"""
    
    def __init__(self):
        self.sort_seq: int = 0          # 消息序号
        self.server_id: int = 0         # 消息 ID，用于关联 voice  
        self.local_type: int = 0        # 消息类型
        self.user_name: str = ""        # 发送人
        self.create_time: int = 0       # 消息创建时间
        self.message_content: bytes = b""  # 消息内容
        self.packed_info_data: bytes = b""  # 额外数据
        self.status: int = 0            # 消息状态


class Message:
    """通用消息结构"""
    
    def __init__(self):
        self.seq: int = 0
        self.time: datetime = datetime.now()
        self.talker: str = ""
        self.talker_name: str = ""
        self.is_chat_room: bool = False
        self.sender: str = ""
        self.sender_name: str = ""
        self.is_self: bool = False
        self.type: int = 0
        self.sub_type: int = 0
        self.content: str = ""
        self.contents: Dict[str, Any] = {}
        self.version: str = "wechatv4"


def parse_packed_info(data: bytes) -> Optional['PackedInfo']:
    """
    解析 PackedInfoData 二进制数据
    
    Args:
        data: 二进制数据
        
    Returns:
        解析后的 PackedInfo 对象，失败返回 None
    """
    if not data:
        return None
        
    try:
        # 尝试使用 protobuf 解析
        if HAS_PROTOBUF:
            packed_info = packedinfo_pb2.PackedInfo()
            packed_info.ParseFromString(data)
            return packed_info
        else:
            # 简单的手动解析实现（仅作为示例）
            # 实际使用时应该使用 protobuf
            print("警告: 使用简化解析，建议生成 protobuf 文件")
            return None
            
    except Exception as e:
        print(f"解析 PackedInfo 失败: {e}")
        return None


def decompress_message_content(content: bytes) -> str:
    """
    解压消息内容
    
    Args:
        content: 可能被压缩的消息内容
        
    Returns:
        解压后的字符串内容
    """
    # 检查是否是 zstd 压缩格式
    zstd_magic = b'\x28\xb5\x2f\xfd'
    
    if content.startswith(zstd_magic):
        if HAS_ZSTD:
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(content)
                return decompressed.decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"zstd 解压失败: {e}")
                return content.decode('utf-8', errors='ignore')
        else:
            print("警告: 检测到 zstd 压缩数据，但 zstandard 包未安装")
            return content.decode('utf-8', errors='ignore')
    else:
        return content.decode('utf-8', errors='ignore')


def wrap_message_v4(msg_v4: MessageV4, talker: str) -> Message:
    """
    将 MessageV4 转换为通用 Message 格式
    这是 Go 代码中 MessageV4.Wrap() 方法的 Python 实现
    
    Args:
        msg_v4: 微信 v4 消息对象
        talker: 聊天对象
        
    Returns:
        转换后的通用消息对象
    """
    # 创建通用消息对象
    message = Message()
    message.seq = msg_v4.sort_seq
    message.time = datetime.fromtimestamp(msg_v4.create_time)
    message.talker = talker
    message.is_chat_room = talker.endswith("@chatroom")
    message.sender = msg_v4.user_name
    message.type = msg_v4.local_type
    message.contents = {}
    message.version = "wechatv4"
    
    # 判断是否是自己发送的消息
    # FIXME: 这个判断可能不够准确
    message.is_self = (msg_v4.status == 2 or 
                      (not message.is_chat_room and talker != msg_v4.user_name))
    
    # 解压消息内容
    content = decompress_message_content(msg_v4.message_content)
    
    # 处理群聊消息的发送者信息
    if message.is_chat_room:
        parts = content.split(":\n", 1)
        if len(parts) == 2:
            message.sender = parts[0]
            content = parts[1]
    
    # 解析媒体信息（这里简化处理，实际应该解析 XML）
    message.content = content
    
    # 语音消息特殊处理
    if message.type == 34:
        message.contents["voice"] = str(msg_v4.server_id)
    
    # 处理 PackedInfoData - 这是核心转换逻辑
    if msg_v4.packed_info_data:
        packed_info = parse_packed_info(msg_v4.packed_info_data)
        if packed_info:
            # 处理图片消息 (Type == 3)
            if message.type == 3 and hasattr(packed_info, 'image') and packed_info.image:
                talker_md5 = hashlib.md5(talker.encode('utf-8')).hexdigest()
                time_format = message.time.strftime("%Y-%m")
                
                # 构建图片文件路径
                img_md5 = packed_info.image.md5
                message.contents["imgfile"] = os.path.join(
                    "msg", "attach", talker_md5, time_format, "Img", f"{img_md5}.dat"
                )
                message.contents["thumb"] = os.path.join(
                    "msg", "attach", talker_md5, time_format, "Img", f"{img_md5}_t.dat"
                )
            
            # 处理视频消息 (Type == 43)
            elif message.type == 43 and hasattr(packed_info, 'video') and packed_info.video:
                time_format = message.time.strftime("%Y-%m")
                
                # 构建视频文件路径
                video_md5 = packed_info.video.md5
                message.contents["videofile"] = os.path.join(
                    "msg", "video", time_format, f"{video_md5}.mp4"
                )
                message.contents["thumb"] = os.path.join(
                    "msg", "video", time_format, f"{video_md5}_thumb.jpg"
                )
    
    return message


def get_media_file_paths(message: Message, host: str = "") -> Dict[str, str]:
    """
    获取消息中的媒体文件路径
    
    Args:
        message: 消息对象
        host: 主机地址
        
    Returns:
        媒体文件路径字典
    """
    paths = {}
    
    if message.type == 3:  # 图片消息
        if "imgfile" in message.contents:
            paths["image"] = f"http://{host}/data/{message.contents['imgfile']}"
        if "thumb" in message.contents:
            paths["thumb"] = f"http://{host}/data/{message.contents['thumb']}"
            
    elif message.type == 43:  # 视频消息
        if "videofile" in message.contents:
            paths["video"] = f"http://{host}/data/{message.contents['videofile']}"
        if "thumb" in message.contents:
            paths["thumb"] = f"http://{host}/data/{message.contents['thumb']}"
            
    elif message.type == 34:  # 语音消息
        if "voice" in message.contents:
            paths["voice"] = f"http://{host}/voice/{message.contents['voice']}"
    
    return paths


def demo_usage():
    """使用示例"""
    # 创建一个模拟的 MessageV4 对象
    msg_v4 = MessageV4()
    msg_v4.sort_seq = 1234567890123
    msg_v4.server_id = 123456
    msg_v4.local_type = 3  # 图片消息
    msg_v4.user_name = "testuser"
    msg_v4.create_time = int(time.time())
    msg_v4.message_content = b"<msg><img md5='abc123'/></msg>"
    msg_v4.status = 2
    
    # 模拟 packed_info_data（实际应该是真实的 protobuf 数据）
    # msg_v4.packed_info_data = b"..." 
    
    # 转换消息
    talker = "friend@example.com"
    message = wrap_message_v4(msg_v4, talker)
    
    print(f"消息类型: {message.type}")
    print(f"发送时间: {message.time}")
    print(f"发送者: {message.sender}")
    print(f"内容: {message.content}")
    print(f"媒体文件: {message.contents}")
    
    # 获取媒体文件路径
    paths = get_media_file_paths(message, "localhost:8080")
    print(f"媒体路径: {paths}")


if __name__ == "__main__":
    demo_usage()
