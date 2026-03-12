#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Analyzer 打包脚本
====================

用法:
    python build_standalone.py
    python build_standalone.py --output ./dist/rdc_analyzer_v1.0
    python build_standalone.py --compress  # 创建 zip 包

输出结构:
    rdc_analyzer_standalone/
    ├── bin/                    # RenderDoc 二进制
    ├── analyzer/               # Python 分析脚本
    ├── run_analyzer.bat        # Windows 启动脚本
    └── README.md               # 使用说明
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime


# ============================================================
# 配置
# ============================================================

# 项目根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent  # scripts/rdc_analyzer/dist -> 项目根

# RenderDoc 构建目录
RENDERDOC_BUILD_DIR = PROJECT_ROOT / "x64" / "Development"
RENDERDOC_PYMODULES = RENDERDOC_BUILD_DIR / "pymodules"

# 需要复制的 RenderDoc 文件
RENDERDOC_BINARIES = [
    "renderdoc.dll",
    "renderdoccmd.exe", 
    "python36.dll",
    "python36.zip",
    "d3dcompiler_47.dll",
    "_ctypes.pyd",
]

# 从 pymodules 复制的文件
PYMODULE_FILES = [
    "renderdoc.pyd",
]

# 排除的 Python 文件模式
PYTHON_EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    "test_*",
    "*_test.py",
    "tests/",
    ".git",
]

# 白名单：只复制这些扩展名的文件（解决报告文件误打包问题）
PYTHON_INCLUDE_EXTENSIONS = [
    ".py",
    ".pyi",      # 类型存根
    ".md",       # 文档
    ".txt",      # requirements.txt 等
    ".toml",     # pyproject.toml
    ".cfg",      # setup.cfg
    ".ini",      # 配置文件
]

# 额外排除的目录（这些目录下的文件即使扩展名匹配也不复制）
PYTHON_EXCLUDE_DIRS = [
    "dist",
    "outputs",
    "output",
    "reports",
    "test_outputs",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "node_modules",
    ".vscode",
    ".idea",
]


# ============================================================
# 工具函数
# ============================================================

def log(msg: str, level: str = "INFO"):
    """打印日志"""
    prefix = {"INFO": "[*]", "OK": "[✓]", "WARN": "[!]", "ERROR": "[✗]"}
    print(f"{prefix.get(level, '[*]')} {msg}")


def copy_file(src: Path, dst: Path):
    """复制文件，显示进度"""
    if not src.exists():
        log(f"文件不存在: {src}", "WARN")
        return False
    
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    size_mb = src.stat().st_size / (1024 * 1024)
    log(f"复制: {src.name} ({size_mb:.1f} MB)")
    return True


def copy_directory(src: Path, dst: Path, exclude_patterns: list = None, 
                   include_extensions: list = None, exclude_dirs: list = None):
    """
    复制目录，支持白名单和黑名单过滤
    
    Args:
        src: 源目录
        dst: 目标目录
        exclude_patterns: 排除的文件模式（黑名单）
        include_extensions: 只复制这些扩展名的文件（白名单，优先级最高）
        exclude_dirs: 排除的目录名（即使扩展名匹配也不复制）
    """
    import fnmatch
    
    if not src.exists():
        log(f"目录不存在: {src}", "WARN")
        return 0
    
    exclude_patterns = exclude_patterns or []
    include_extensions = include_extensions or []
    exclude_dirs = exclude_dirs or []
    
    copied = 0
    skipped_by_ext = 0
    skipped_by_dir = 0
    
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        
        relative = item.relative_to(src)
        
        # 1. 检查目录黑名单
        path_parts = relative.parts
        in_excluded_dir = False
        for part in path_parts[:-1]:  # 不检查文件名本身
            if part in exclude_dirs:
                in_excluded_dir = True
                break
        if in_excluded_dir:
            skipped_by_dir += 1
            continue
        
        # 2. 检查扩展名白名单（如果设置了白名单，只复制白名单中的扩展名）
        if include_extensions:
            ext = item.suffix.lower()
            if ext not in include_extensions:
                skipped_by_ext += 1
                continue
        
        # 3. 检查文件名模式黑名单
        skip = False
        for pattern in exclude_patterns:
            if pattern.endswith("/"):
                # 目录模式
                if pattern.rstrip("/") in str(relative.parent):
                    skip = True
                    break
            elif "*" in pattern:
                # 通配符模式
                if fnmatch.fnmatch(item.name, pattern):
                    skip = True
                    break
            else:
                # 精确匹配
                if pattern in str(relative):
                    skip = True
                    break
        
        if skip:
            continue
        
        dst_file = dst / relative
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dst_file)
        copied += 1
    
    if skipped_by_ext > 0:
        log(f"按扩展名过滤跳过: {skipped_by_ext} 个文件")
    if skipped_by_dir > 0:
        log(f"按目录过滤跳过: {skipped_by_dir} 个文件")
    
    return copied


# ============================================================
# 主打包逻辑
# ============================================================

def build_standalone(output_dir: Path, compress: bool = False):
    """构建独立发布包"""
    
    log(f"开始构建独立发布包...")
    log(f"输出目录: {output_dir}")
    
    # 清理目标目录
    if output_dir.exists():
        log(f"清理已存在的目录: {output_dir}")
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建 bin 目录
    bin_dir = output_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 复制 RenderDoc 二进制文件
    log("=" * 50)
    log("复制 RenderDoc 二进制文件...")
    
    for filename in RENDERDOC_BINARIES:
        src = RENDERDOC_BUILD_DIR / filename
        dst = bin_dir / filename
        if not copy_file(src, dst):
            log(f"缺少必要文件: {filename}", "ERROR")
            return False
    
    # 2. 复制 Python 模块
    log("=" * 50)
    log("复制 Python 模块...")
    
    for filename in PYMODULE_FILES:
        src = RENDERDOC_PYMODULES / filename
        dst = bin_dir / filename
        if not copy_file(src, dst):
            log(f"缺少必要文件: {filename}", "ERROR")
            return False
    
    # 3. 复制分析器脚本
    log("=" * 50)
    log("复制分析器脚本...")
    
    analyzer_src = SCRIPT_DIR.parent  # scripts/rdc_analyzer/
    analyzer_dst = output_dir / "analyzer"
    
    copied = copy_directory(
        analyzer_src, 
        analyzer_dst,
        exclude_patterns=PYTHON_EXCLUDE_PATTERNS + ["dist/"],
        include_extensions=PYTHON_INCLUDE_EXTENSIONS,
        exclude_dirs=PYTHON_EXCLUDE_DIRS
    )
    log(f"复制了 {copied} 个 Python 文件", "OK")
    
    # 4. 复制启动脚本
    log("=" * 50)
    log("复制启动脚本...")
    
    run_script_src = SCRIPT_DIR / "run_analyzer.bat"
    run_script_dst = output_dir / "run_analyzer.bat"
    if run_script_src.exists():
        shutil.copy2(run_script_src, run_script_dst)
        log("复制: run_analyzer.bat", "OK")
    else:
        log("启动脚本不存在，将创建默认版本", "WARN")
    
    # 5. 创建 README
    log("=" * 50)
    log("创建 README.md...")
    
    readme_content = generate_readme()
    readme_path = output_dir / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")
    log("创建: README.md", "OK")
    
    # 6. 统计大小
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    total_size_mb = total_size / (1024 * 1024)
    
    log("=" * 50)
    log(f"构建完成!", "OK")
    log(f"总大小: {total_size_mb:.1f} MB")
    log(f"位置: {output_dir}")
    
    # 7. 可选压缩
    if compress:
        log("=" * 50)
        log("创建压缩包...")
        
        zip_name = output_dir.name
        zip_path = output_dir.parent / f"{zip_name}.zip"
        
        shutil.make_archive(
            str(output_dir.parent / zip_name),
            'zip',
            output_dir.parent,
            output_dir.name
        )
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        log(f"压缩包: {zip_path} ({zip_size_mb:.1f} MB)", "OK")
    
    return True


def generate_readme() -> str:
    """生成 README 文档"""
    return f"""# RDC Analyzer - 独立发布包

> 构建时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 快速开始

### Windows

```cmd
:: 分析 RDC 文件
run_analyzer.bat analyze D:\\captures\\game.rdc -o ./output

:: 提取资源 (纹理、Shader)
run_analyzer.bat extract-resources D:\\captures\\game.rdc --all

:: 查看帮助
run_analyzer.bat --help
```

## 系统要求

- **操作系统**: Windows 10/11 x64
- **Python**: Python 3.6（如果 bin 目录不含 python.exe）
- **GPU**: 支持 D3D11/D3D12/Vulkan/OpenGL 的显卡

## 目录结构

```
rdc_analyzer_standalone/
├── bin/                    # RenderDoc 核心组件
│   ├── renderdoc.dll       # 核心引擎
│   ├── renderdoc.pyd       # Python 绑定
│   ├── renderdoccmd.exe    # 命令行工具
│   └── ...
├── analyzer/               # Python 分析脚本
├── run_analyzer.bat        # 启动脚本
└── README.md               # 本文档
```

## 可用命令

| 命令 | 说明 |
|------|------|
| `analyze` | 分析 RDC 文件，生成 HTML/JSON 报告 |
| `extract-resources` | 提取纹理、Shader、RT 快照 |
| `compare` | 对比两个帧的性能差异 |
| `rules` | 列出可用的分析规则 |

## 常见问题

### Q: 提示找不到 Python 3.6

RenderDoc 的 Python 绑定需要 Python 3.6。请安装:
https://www.python.org/downloads/release/python-368/

### Q: 打开 RDC 文件失败

可能的原因：
1. RDC 文件版本不兼容（需要相同或兼容版本的 RenderDoc 捕获）
2. 跨 GPU 厂商回放（如在 NVIDIA 上回放 Mali 捕获）
3. 文件损坏

### Q: 如何在代码中使用

```python
import sys
sys.path.insert(0, "./bin")
sys.path.insert(0, "./analyzer")

# 设置 DLL 路径 (Python 3.8+)
import os
os.add_dll_directory("./bin")

# 使用分析器
from analyzer.pipeline import analyze_rdc
result = analyze_rdc("capture.rdc")
```

## 版权声明

本工具基于 RenderDoc 开发，RenderDoc 使用 MIT 许可证。
https://github.com/baldurk/renderdoc
"""


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="构建 RDC Analyzer 独立发布包"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出目录 (默认: ./rdc_analyzer_standalone)"
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="创建 zip 压缩包"
    )
    parser.add_argument(
        "--renderdoc-dir",
        default=None,
        help="RenderDoc 构建目录 (默认: 项目的 x64/Development)"
    )
    
    args = parser.parse_args()
    
    # 确定输出目录
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = SCRIPT_DIR / "rdc_analyzer_standalone"
    
    # 覆盖 RenderDoc 目录
    global RENDERDOC_BUILD_DIR, RENDERDOC_PYMODULES
    if args.renderdoc_dir:
        RENDERDOC_BUILD_DIR = Path(args.renderdoc_dir).resolve()
        RENDERDOC_PYMODULES = RENDERDOC_BUILD_DIR / "pymodules"
    
    # 检查 RenderDoc 目录
    if not RENDERDOC_BUILD_DIR.exists():
        log(f"RenderDoc 构建目录不存在: {RENDERDOC_BUILD_DIR}", "ERROR")
        log("请先构建 RenderDoc 或使用 --renderdoc-dir 指定目录")
        sys.exit(1)
    
    # 构建
    success = build_standalone(output_dir, compress=args.compress)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
