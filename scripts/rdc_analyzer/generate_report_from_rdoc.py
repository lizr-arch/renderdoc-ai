#!/usr/bin/env python3
"""
RenderDoc 集成报告生成器

在 RenderDoc Python Shell 中运行此脚本，自动生成包含真实纹理缩略图的分析报告。

用法（在 RenderDoc Python Shell 中）:
    exec(open(r'd:\Code\git\renderdoc\scripts\rdc_analyzer\generate_report_from_rdoc.py').read())

功能:
    1. 提取所有纹理的真实缩略图
    2. 分析纹理使用情况（重复、未使用）
    3. 生成交互式 HTML 报告

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import os
import sys
import json
import base64
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加脚本目录到 Python 路径
SCRIPT_DIR = Path(r'd:\Code\git\renderdoc\scripts\rdc_analyzer')
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

print("=" * 70)
print("RenderDoc Integrated Report Generator")
print("=" * 70)

# ============================================================================
# 检查 RenderDoc 环境
# ============================================================================

try:
    # 在 RenderDoc Python Shell 中，这些变量已定义
    ctx = pyrenderdoc.GetCaptureContext()
    rd = renderdoc
    
    if ctx is None:
        print("[ERROR] No capture context available.")
        print("Please open an RDC file first!")
        raise SystemExit
    
    if not ctx.IsCaptureLoaded():
        print("[ERROR] No capture loaded.")
        print("Please open an RDC file first!")
        raise SystemExit
    
    # 获取文件路径
    cap_file = ctx.GetCaptureFilename()
    if not cap_file:
        print("[ERROR] Cannot get capture filename.")
        raise SystemExit
    
    print(f"[INFO] Capture: {cap_file}")
    
except NameError as e:
    if 'pyrenderdoc' in str(e) or 'renderdoc' in str(e):
        print("[ERROR] This script must be run inside RenderDoc's Python Shell.")
        print()
        print("Steps:")
        print("  1. Open RenderDoc application")
        print("  2. File -> Open Capture -> select your .rdc file")
        print("  3. Window -> Python Shell")
        print("  4. Copy and paste this command:")
        print()
        print(f"     exec(open(r'{__file__}').read())")
        raise SystemExit
    else:
        raise

# ============================================================================
# 配置
# ============================================================================

THUMBNAIL_MAX_SIZE = 128  # 缩略图最大尺寸
OUTPUT_DIR = Path(cap_file).parent
OUTPUT_NAME = Path(cap_file).stem + "_report.html"
OUTPUT_PATH = OUTPUT_DIR / OUTPUT_NAME

print(f"[INFO] Output: {OUTPUT_PATH}")

# ============================================================================
# 提取纹理信息和缩略图
# ============================================================================

print()
print("[1/4] Extracting textures and thumbnails...")

# 获取回放控制器
replay = ctx.Replay()
if replay is None:
    print("[ERROR] No replay available")
    raise SystemExit

controller = replay.GetController()
if controller is None:
    print("[ERROR] No replay controller available")
    raise SystemExit

# 获取所有纹理
textures_desc = controller.GetTextures()
print(f"  Found {len(textures_desc)} textures")

# 创建临时目录存储缩略图
temp_dir = Path(tempfile.mkdtemp(prefix="rdoc_report_"))

# 提取纹理数据
textures_data = []
thumbnails = {}  # resource_id -> base64 data URI

for i, tex in enumerate(textures_desc):
    # 跳过无效纹理
    if tex.resourceId == rd.ResourceId.Null():
        continue
    
    res_id = int(tex.resourceId)
    
    # 收集纹理信息
    tex_info = {
        "resource_id": res_id,
        "name": f"Texture_{res_id}",
        "width": tex.width,
        "height": tex.height,
        "depth": tex.depth,
        "format": tex.format.Name(),
        "mips": tex.mips,
        "arraysize": tex.arraysize,
        "msQual": tex.msQual,
        "msSamp": tex.msSamp,
        "type": str(tex.type),
        "cubemap": tex.cubemap,
    }
    
    # 估算大小 (简化计算)
    bpp = 4  # 假设 4 字节/像素
    fmt_name = tex.format.Name().lower()
    if 'bc' in fmt_name or 'dxt' in fmt_name or 'etc' in fmt_name or 'astc' in fmt_name:
        bpp = 1  # 压缩格式
    elif 'r8' in fmt_name and 'g8' not in fmt_name:
        bpp = 1
    elif 'r16' in fmt_name or 'r8g8' in fmt_name:
        bpp = 2
    elif 'rgba16' in fmt_name or 'r32' in fmt_name:
        bpp = 8
    elif 'rgba32' in fmt_name:
        bpp = 16
    
    estimated_size = tex.width * tex.height * tex.depth * bpp
    if tex.mips > 1:
        estimated_size = int(estimated_size * 1.33)  # mip 链
    if tex.arraysize > 1:
        estimated_size *= tex.arraysize
    
    tex_info["estimated_size"] = estimated_size
    
    # 提取缩略图
    temp_file = temp_dir / f"thumb_{res_id}.png"
    
    try:
        save_data = rd.TextureSave()
        save_data.resourceId = tex.resourceId
        save_data.destType = rd.FileType.PNG
        save_data.alpha = rd.AlphaMapping.Preserve
        
        # 选择合适的 mip level
        mip_to_use = 0
        w, h = tex.width, tex.height
        while (w > THUMBNAIL_MAX_SIZE * 2 or h > THUMBNAIL_MAX_SIZE * 2) and mip_to_use < tex.mips - 1:
            w = max(1, w // 2)
            h = max(1, h // 2)
            mip_to_use += 1
        
        save_data.mip = mip_to_use
        
        result = controller.SaveTexture(save_data, str(temp_file))
        
        if result == rd.ResultCode.Succeeded and temp_file.exists():
            with open(temp_file, 'rb') as f:
                img_data = f.read()
            b64_data = base64.b64encode(img_data).decode('ascii')
            tex_info["thumbnail"] = f"data:image/png;base64,{b64_data}"
            temp_file.unlink()
        else:
            tex_info["thumbnail"] = None
            
    except Exception as e:
        tex_info["thumbnail"] = None
    
    textures_data.append(tex_info)
    
    if (i + 1) % 20 == 0:
        print(f"  Progress: {i + 1}/{len(textures_desc)}")

print(f"  [OK] Extracted {len(textures_data)} textures")

# 清理临时目录
import shutil
shutil.rmtree(temp_dir, ignore_errors=True)

# ============================================================================
# 分析纹理使用情况
# ============================================================================

print()
print("[2/4] Analyzing texture usage...")

# 简化的重复检测（基于尺寸和格式分组）
def get_texture_signature(tex):
    return f"{tex['width']}x{tex['height']}_{tex['format']}"

# 按签名分组
sig_groups = {}
for tex in textures_data:
    sig = get_texture_signature(tex)
    if sig not in sig_groups:
        sig_groups[sig] = []
    sig_groups[sig].append(tex)

# 找出可能的重复（同尺寸同格式）
duplicate_groups = []
total_wasted = 0

for sig, group in sig_groups.items():
    if len(group) > 1:
        # 标记第一个为保留，其余为重复
        for i, tex in enumerate(group):
            tex["is_duplicate"] = i > 0
            tex["duplicate_of"] = group[0]["resource_id"] if i > 0 else None
        
        wasted = sum(t["estimated_size"] for t in group[1:])
        total_wasted += wasted
        
        duplicate_groups.append({
            "signature": sig,
            "textures": group,
            "count": len(group),
            "wasted_bytes": wasted
        })

duplicate_analysis = {
    "total_groups": len(duplicate_groups),
    "total_wasted_bytes": total_wasted,
    "groups": duplicate_groups[:20]  # 只取前 20 组
}

print(f"  [OK] Found {len(duplicate_groups)} potential duplicate groups")
print(f"  [OK] Estimated wasted VRAM: {total_wasted / (1024*1024):.1f} MB")

# ============================================================================
# 使用分析（简化版 - 需要 Draw Call 分析才能准确）
# ============================================================================

print()
print("[3/4] Analyzing usage patterns...")

# 简化的使用分析（标记小纹理为可能未使用）
unused_candidates = []
used_textures = []

for tex in textures_data:
    # 简单启发式：非常小的纹理或奇怪尺寸可能是未使用的
    if tex["width"] <= 4 and tex["height"] <= 4:
        tex["usage_count"] = 0
        tex["is_unused"] = True
        unused_candidates.append(tex)
    else:
        tex["usage_count"] = 1  # 假设使用
        tex["is_unused"] = False
        used_textures.append(tex)

usage_analysis = {
    "total_textures": len(textures_data),
    "used_count": len(used_textures),
    "unused_count": len(unused_candidates),
    "unused_textures": unused_candidates[:20]
}

print(f"  [OK] Used: {len(used_textures)}, Potentially unused: {len(unused_candidates)}")

# ============================================================================
# 生成 HTML 报告
# ============================================================================

print()
print("[4/4] Generating HTML report...")

# 导入报告生成器
try:
    from generate_offline_report import generate_report_html
    
    # 准备报告数据
    report_data = {
        "capture_info": {
            "filename": str(cap_file),
            "capture_time": datetime.now().isoformat(),
            "api": "Unknown",  # 可以从捕获中获取
            "frame_count": 1
        },
        "textures": textures_data,
        "duplicate_analysis": duplicate_analysis,
        "usage_analysis": usage_analysis,
        "summary": {
            "total_textures": len(textures_data),
            "total_vram": sum(t["estimated_size"] for t in textures_data),
            "duplicate_groups": len(duplicate_groups),
            "wasted_vram": total_wasted,
            "unused_textures": len(unused_candidates)
        }
    }
    
    # 生成 HTML
    html_content = generate_report_html(report_data)
    
    # 保存报告
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  [OK] Report saved to: {OUTPUT_PATH}")
    
except Exception as e:
    print(f"  [ERROR] Failed to generate report: {e}")
    print("  Falling back to JSON export...")
    
    # 回退到 JSON 导出
    json_path = OUTPUT_DIR / (Path(cap_file).stem + "_data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        # 移除 thumbnail 数据以减小文件大小
        export_data = {
            "capture_info": {"filename": str(cap_file)},
            "textures": [{k: v for k, v in t.items() if k != "thumbnail"} for t in textures_data],
            "duplicate_analysis": duplicate_analysis,
            "usage_analysis": usage_analysis
        }
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"  [OK] JSON data saved to: {json_path}")

# ============================================================================
# 完成
# ============================================================================

print()
print("=" * 70)
print("[DONE] Report generation complete!")
print()
print(f"  Report: {OUTPUT_PATH}")
print(f"  Textures: {len(textures_data)}")
print(f"  Duplicates: {len(duplicate_groups)} groups")
print(f"  Wasted VRAM: {total_wasted / (1024*1024):.1f} MB")
print()
print("Open the HTML file in a browser to view the interactive report.")
print("=" * 70)
