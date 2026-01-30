# 方案 C：捕获时预导出纹理 - 实现计划

> **日期**: 2025-01-20 18:00  
> **Agent**: Agent01  
> **状态**: 规划中

---

## 1. Scope / 范围

### 目标
在 Android 设备上捕获 RDC 后，立即在设备端导出纹理，绕过 PC 端 GPU 兼容性问题。

### 交付物
1. Android 版 `renderdoccmd` 可执行文件 (arm64-v8a)
2. 部署脚本 `deploy_android.sh`
3. 自动导出脚本 `post_capture_export.sh`
4. 更新后的 `analyze_rdc.py`（支持预导出纹理）

### 不在范围内
- 修改 RenderDoc 核心源码（已完成 export 命令）
- 自动化 CI/CD 集成（后续任务）

---

## 2. Assumptions / 假设

1. 用户已安装 Android NDK（r21+ 推荐）
2. Android 设备已 root 或可执行 `/data/local/tmp/` 下的二进制
3. PC 与设备通过 adb 连接

---

## 3. Build / Test / Lint Quick Guide

> **注意**: 以下命令仅记录，需用户手动执行

### Android 编译
```bash
# 设置 NDK 路径
export ANDROID_NDK=/path/to/android-ndk-r25c

# CMake 配置
cmake -B build-android \
    -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-26 \
    -DBUILD_ANDROID=On \
    -DCMAKE_BUILD_TYPE=Release

# 编译
cmake --build build-android --target renderdoccmd -j8
```

### 部署测试
```bash
# 推送到设备
adb push build-android/bin/renderdoccmd /data/local/tmp/
adb shell chmod +x /data/local/tmp/renderdoccmd

# 验证
adb shell /data/local/tmp/renderdoccmd export --help
```

### Python 测试
```bash
python analyze_rdc.py test.rdc --textures ./textures/ --output report.html
```

---

## 4. Task Checklist / 任务清单

### 阶段 1: Android 编译 (预计 30 分钟)

- [ ] **1.1** 检查 RenderDoc Android 构建配置
  - 文件: `CMakeLists.txt`, `renderdoccmd/CMakeLists.txt`
  - 验证: `BUILD_ANDROID` 选项存在

- [ ] **1.2** 创建 Android 编译脚本
  - 输出: `scripts/build_android.sh`
  - 内容: NDK 路径设置 + CMake 配置 + 编译命令

- [ ] **1.3** 编译 Android 版 renderdoccmd
  - 输出: `build-android/bin/renderdoccmd`
  - 验证: `file` 命令确认 ARM64 ELF

### 阶段 2: 部署脚本 (预计 15 分钟)

- [ ] **2.1** 创建部署脚本
  - 输出: `scripts/deploy_android.sh`
  - 功能: adb push + chmod + 验证

- [ ] **2.2** 测试部署
  - 验证: `adb shell /data/local/tmp/renderdoccmd --version`

### 阶段 3: Post-Capture 脚本 (预计 20 分钟)

- [ ] **3.1** 创建自动导出脚本
  - 输出: `scripts/post_capture_export.sh`
  - 功能: 监控 RDC 文件 → 调用 export → 输出纹理

- [ ] **3.2** 创建一键工作流脚本
  - 输出: `scripts/capture_and_export.sh`
  - 功能: 捕获 + 导出 + 拉取到 PC

### 阶段 4: Python 脚本更新 (预计 20 分钟)

- [ ] **4.1** 修改 analyze_rdc.py
  - 添加 `--textures` 参数
  - 支持从目录读取预导出纹理
  - 跳过 GPU 回放逻辑

- [ ] **4.2** 更新 HTML 模板
  - 支持外部纹理文件路径

### 阶段 5: 端到端测试 (预计 30 分钟)

- [ ] **5.1** 准备测试环境
  - Android 设备连接
  - 测试游戏安装

- [ ] **5.2** 执行完整流程测试
  - 捕获 → 设备端导出 → adb pull → 生成报告
  - 验证: 报告中显示真实纹理

---

## 5. Risks / Blockers / 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| NDK 版本不兼容 | 编译失败 | 使用 r21-r25 稳定版本 |
| 设备权限不足 | 无法执行 | 使用 root 或 adb shell run-as |
| 存储空间不足 | 导出失败 | 添加空间检查，支持 --max-size |
| Vulkan 驱动问题 | 回放失败 | 日志诊断，回退到元数据模式 |

---

## 6. Decisions / 决策记录

| 决策 | 原因 |
|------|------|
| 使用 arm64-v8a 作为主要架构 | 覆盖 99% 现代 Android 设备 |
| 脚本使用 Shell 而非 Python | Android 设备兼容性更好 |
| 默认导出 PNG 格式 | 兼容性最好，报告可直接使用 |

---

## 7. Verification / Acceptance / 验收标准

### Definition of Done

1. ✅ Android 版 renderdoccmd 编译成功
2. ✅ 可在 Android 设备上执行 `export --help`
3. ✅ 可导出 RDC 中的纹理到设备存储
4. ✅ analyze_rdc.py 可读取预导出纹理生成报告
5. ✅ 端到端流程验证通过

### 测试用例

```bash
# 测试 1: Android 端导出
adb shell /data/local/tmp/renderdoccmd export \
    --out=/sdcard/RenderDoc/textures \
    --metadata \
    /sdcard/RenderDoc/capture.rdc

# 测试 2: PC 端生成报告
adb pull /sdcard/RenderDoc/ ./local/
python analyze_rdc.py ./local/capture.rdc \
    --textures ./local/textures/ \
    --output report.html
```

---

## 8. Next Steps / 后续步骤

1. 用户确认 NDK 环境
2. 开始阶段 1 编译任务
3. 逐步验证每个阶段

---

## 附录 A: 脚本模板

### build_android.sh

```bash
#!/bin/bash
set -e

# 检查 NDK
if [ -z "$ANDROID_NDK" ]; then
    echo "Error: ANDROID_NDK not set"
    echo "Usage: export ANDROID_NDK=/path/to/ndk && ./build_android.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$ROOT_DIR/build-android"

echo "=== Building RenderDoc for Android ==="
echo "NDK: $ANDROID_NDK"
echo "Build dir: $BUILD_DIR"

# CMake 配置
cmake -B "$BUILD_DIR" -S "$ROOT_DIR" \
    -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-26 \
    -DBUILD_ANDROID=On \
    -DCMAKE_BUILD_TYPE=Release

# 编译
cmake --build "$BUILD_DIR" --target renderdoccmd -j$(nproc)

echo "=== Build complete ==="
echo "Output: $BUILD_DIR/bin/renderdoccmd"
```

### deploy_android.sh

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$ROOT_DIR/build-android"
BINARY="$BUILD_DIR/bin/renderdoccmd"
REMOTE_PATH="/data/local/tmp/renderdoccmd"

if [ ! -f "$BINARY" ]; then
    echo "Error: $BINARY not found. Run build_android.sh first."
    exit 1
fi

echo "=== Deploying to Android device ==="

# 推送
adb push "$BINARY" "$REMOTE_PATH"

# 设置权限
adb shell chmod +x "$REMOTE_PATH"

# 验证
echo "=== Verifying installation ==="
adb shell "$REMOTE_PATH" --version

echo "=== Deployment complete ==="
```

### post_capture_export.sh (设备端运行)

```bash
#!/system/bin/sh
# 在 Android 设备上运行的导出脚本

RDC_FILE="$1"
RENDERDOCCMD="/data/local/tmp/renderdoccmd"

if [ -z "$RDC_FILE" ]; then
    echo "Usage: post_capture_export.sh <rdc_file>"
    exit 1
fi

if [ ! -f "$RDC_FILE" ]; then
    echo "Error: RDC file not found: $RDC_FILE"
    exit 1
fi

# 创建输出目录
OUT_DIR="${RDC_FILE%.rdc}_textures"
mkdir -p "$OUT_DIR"

echo "Exporting textures from: $RDC_FILE"
echo "Output directory: $OUT_DIR"

# 执行导出
$RENDERDOCCMD export \
    --out="$OUT_DIR" \
    --format=png \
    --metadata \
    "$RDC_FILE"

echo "Export complete!"
ls -la "$OUT_DIR"
```

---

## 附录 B: analyze_rdc.py 修改点

```python
# 新增参数
parser.add_argument('--textures', type=str, 
    help='预导出纹理目录路径，跳过 GPU 回放')

# 修改纹理加载逻辑
def load_textures(rdc_path, textures_dir=None):
    if textures_dir and os.path.exists(textures_dir):
        # 从预导出目录加载
        return load_preexported_textures(textures_dir)
    else:
        # 尝试 GPU 回放导出（可能失败）
        return export_via_replay(rdc_path)

def load_preexported_textures(textures_dir):
    """从预导出目录加载纹理"""
    result = {}
    
    # 读取 metadata
    meta_path = os.path.join(textures_dir, 'textures.json')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        
        for tex in meta.get('textures', []):
            tex_path = os.path.join(textures_dir, tex['file'])
            if os.path.exists(tex_path):
                # 转为 base64 嵌入 HTML
                with open(tex_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode()
                result[tex['id']] = {
                    'name': tex['name'],
                    'width': tex['width'],
                    'height': tex['height'],
                    'format': tex['format'],
                    'thumbnail': f'data:image/png;base64,{b64}'
                }
    
    return result
```
