# 微信 v4 消息解析模块

此模块将 Go 版本的 `PackedInfoData` 解析逻辑转换为 Python 实现，用于处理微信 v4 版本的消息数据。

## 功能特性

- ✅ 解析微信 v4 版本的 `packed_info_data` 字段
- ✅ 处理图片消息的文件路径生成
- ✅ 处理视频消息的文件路径生成  
- ✅ 支持 zstd 压缩消息内容的解压
- ✅ 完整的消息类型转换
- ✅ 兼容原 Go 版本的逻辑

## 安装依赖

```bash
# 安装必要的依赖包
pip install -r requirements_v4.txt

# 生成 protobuf Python 代码
python generate_proto.py
```

## 使用方法

### 基本使用

```python
from py.v4 import wrap_message_v4, MessageV4

# 创建 MessageV4 对象（通常来自数据库查询）
msg_v4 = MessageV4()
msg_v4.sort_seq = 1234567890123
msg_v4.local_type = 3  # 图片消息
msg_v4.user_name = "sender@example.com"
msg_v4.create_time = 1640995200  # Unix 时间戳
msg_v4.message_content = b'<msg><img md5="abc123"/></msg>'
msg_v4.packed_info_data = b"..."  # 来自数据库的二进制数据

# 转换为通用消息格式
talker = "friend@example.com"
message = wrap_message_v4(msg_v4, talker)

# 查看结果
print(f"消息类型: {message.type}")
print(f"发送时间: {message.time}")
print(f"媒体文件: {message.contents}")
```

### 获取媒体文件路径

```python
from py.v4 import get_media_file_paths

# 获取消息中的媒体文件访问路径
paths = get_media_file_paths(message, host="localhost:8080")
print(paths)
# 输出: {'image': 'http://localhost:8080/data/msg/attach/.../img.dat'}
```

### 消息内容解压

```python
from py.v4 import decompress_message_content

# 解压可能被 zstd 压缩的消息内容
compressed_content = b'\x28\xb5\x2f\xfd...'  # zstd 压缩数据
decompressed = decompress_message_content(compressed_content)
print(decompressed)
```

## 文件结构

```
py/v4/
├── __init__.py              # 包初始化文件
├── message_parser.py        # 核心解析模块
├── packedinfo.proto         # protobuf 定义文件
├── generate_proto.py        # protobuf 编译脚本
├── requirements_v4.txt      # 依赖包列表
├── test_example.py          # 使用示例和测试
└── README.md               # 说明文档
```

## 核心功能对照

### Go 代码 vs Python 代码

| Go 功能 | Python 实现 | 说明 |
|---------|-------------|------|
| `MessageV4.Wrap()` | `wrap_message_v4()` | 消息格式转换 |
| `ParsePackedInfo()` | `parse_packed_info()` | protobuf 数据解析 |
| zstd 解压 | `decompress_message_content()` | 消息内容解压 |
| 文件路径生成 | `message.contents` | 媒体文件路径 |

### 消息类型支持

| 类型 | 值 | 描述 | Python 支持 |
|------|----|----- |-------------|
| 文本 | 1 | 普通文本消息 | ✅ |
| 图片 | 3 | 图片消息 | ✅ |
| 语音 | 34 | 语音消息 | ✅ |
| 视频 | 43 | 视频消息 | ✅ |

## 运行测试

```bash
# 运行测试示例
python test_example.py
```

测试输出将包括：
- 消息转换测试
- 媒体文件路径生成测试
- zstd 解压测试
- 文件路径示例

## 注意事项

1. **protobuf 依赖**: 需要先运行 `python generate_proto.py` 生成 protobuf Python 代码
2. **真实数据**: 示例中的 `packed_info_data` 是模拟数据，实际使用时需要从数据库获取
3. **压缩支持**: zstd 解压需要安装 `zstandard` 包
4. **文件路径**: 生成的文件路径与 Go 版本完全一致

## 与 Go 版本的差异

1. **错误处理**: Python 版本使用异常处理，Go 版本使用错误返回值
2. **类型系统**: Python 使用动态类型，Go 使用静态类型
3. **内存管理**: Python 自动垃圾回收，Go 手动内存管理

## 依赖包说明

- `protobuf`: 用于解析 packed_info_data 中的 protobuf 数据
- `zstandard`: 用于解压 zstd 格式的消息内容（可选）

## 故障排除

### 常见问题

1. **ImportError**: 确保安装了所有依赖包
2. **protobuf 解析失败**: 检查是否生成了 `packedinfo_pb2.py` 文件
3. **路径错误**: 确保导入路径正确

### 调试模式

在 `message_parser.py` 中设置调试标志来查看详细信息：

```python
# 在文件顶部添加
DEBUG = True
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进此模块。

## 许可证

与主项目保持一致的许可证。
