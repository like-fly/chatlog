# WeChat Dat Converter - Object-Oriented API

## 概述

这是一个全新的面向对象版本的微信 dat 文件转换器，相比原始的函数式API，提供了更清晰、更灵活的接口。

## 主要改进

### 1. 面向对象设计
- **清晰的状态管理**：AES密钥和XOR密钥通过构造函数传入，避免全局变量
- **更好的封装**：相关功能组织在同一个类中
- **易于扩展**：可以轻松添加新的格式支持或转换选项

### 2. 改进的API设计
```python
# 旧API - 使用全局变量
from dat2img import dat2image, set_aes_key, scan_and_set_xor_key
set_aes_key("32666261386464653536643364353161")
scan_and_set_xor_key(data_dir)
result, ext = dat2image(data)

# 新API - 面向对象
from dat2img.converter import WeChatDatConverter
converter = WeChatDatConverter(
    aes_key="32666261386464653536643364353161",
    xor_key=0xaf
)
result, ext = converter.convert(data)
```

### 3. 增强的功能

#### 文件级操作
```python
# 直接转换文件
output_path = converter.convert_file("input.dat", "output.jpg")

# 自动确定输出路径和扩展名
output_path = converter.convert_file("input.dat")
```

#### 批量转换
```python
# 批量转换整个目录
results = converter.batch_convert(
    input_dir="D:/wechat/images", 
    output_dir="D:/converted",
    preserve_structure=True  # 保持目录结构
)

# 获取转换结果统计
success_count = sum(1 for _, _, ok in results if ok)
```

#### 自动密钥检测
```python
# 自动检测XOR密钥
xor_key = WeChatDatConverter.scan_xor_key("D:/wechat/attach")
converter = WeChatDatConverter(aes_key="...", xor_key=xor_key)
```

### 4. 更好的错误处理
- **类型安全**：使用类型注解，支持静态类型检查
- **详细的异常信息**：每个步骤都有明确的错误说明
- **优雅的降级**：WXGF转换失败时自动返回h265格式

### 5. 修复的问题
- **FFmpeg路径问题**：正确处理Windows下的ffmpeg.exe路径
- **权限问题**：改进了subprocess调用，避免权限错误
- **内存效率**：优化了大文件的处理

## 使用示例

### 基本使用
```python
from dat2img.converter import WeChatDatConverter

# 初始化转换器
converter = WeChatDatConverter(
    aes_key="32666261386464653536643364353161",
    xor_key=0xaf,
    ffmpeg_path="C:/ffmpeg/bin"  # 可选，自动检测
)

# 转换单个文件
output = converter.convert_file("image.dat")
print(f"转换完成: {output}")
```

### 批量转换
```python
# 批量转换并保持目录结构
results = converter.batch_convert(
    input_dir="D:/微信文件/images",
    output_dir="D:/converted_images",
    preserve_structure=True
)

# 统计结果
total = len(results)
success = sum(1 for _, _, ok in results if ok)
print(f"转换完成: {success}/{total}")
```

### 自动配置
```python
# 自动检测XOR密钥
data_dir = "D:/微信文件/wxid_xxx/msg/attach"
xor_key = WeChatDatConverter.scan_xor_key(data_dir)

# 使用检测到的密钥
converter = WeChatDatConverter(
    aes_key="your_aes_key_here",
    xor_key=xor_key
)
```

## 性能对比

| 功能 | 旧API | 新API |
|------|--------|--------|
| 单文件转换 | ✓ | ✓ |
| 批量转换 | 手动循环 | 内置支持 |
| 错误处理 | 基础 | 增强 |
| 类型安全 | 无 | ✓ |
| 状态管理 | 全局变量 | 实例变量 |
| FFmpeg支持 | 部分问题 | 完全修复 |
| 内存使用 | 标准 | 优化 |

## 兼容性

新API完全向后兼容，现有的代码可以继续使用旧API，同时新项目建议使用新的面向对象API。

## 依赖要求

- Python 3.7+
- pycryptodome
- pathlib (Python 3.4+内置)
- FFmpeg (用于WXGF转换)

## 安装FFmpeg

### Windows
1. 下载FFmpeg: https://ffmpeg.org/download.html
2. 解压到目录如 `C:/ffmpeg`
3. 设置环境变量 `FFMPEG_PATH=C:/ffmpeg/bin`
4. 或在代码中指定: `WeChatDatConverter(ffmpeg_path="C:/ffmpeg/bin")`

### 验证安装
```bash
ffmpeg -version
```

## 故障排除

### 常见问题

1. **"FFmpeg not found"**
   - 确保FFmpeg已安装并在PATH中
   - 或使用 `ffmpeg_path` 参数指定路径

2. **"Permission denied"**
   - 检查输出目录权限
   - 确保FFmpeg有执行权限

3. **"No partition found"**
   - 文件可能不是WXGF格式
   - 检查AES密钥是否正确

4. **转换为h265而不是jpg**
   - FFmpeg转换失败，但h265数据有效
   - 可以用其他工具进一步转换h265文件

### 调试建议

```python
# 启用详细错误信息
try:
    result = converter.convert(data)
except Exception as e:
    print(f"转换失败: {e}")
    import traceback
    traceback.print_exc()
```

## 贡献

欢迎提交issue和pull request来改进这个工具。
