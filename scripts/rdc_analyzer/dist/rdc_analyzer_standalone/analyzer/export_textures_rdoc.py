#!/usr/bin/env python3
"""
RenderDoc Python Shell 快捷脚本

在 RenderDoc 中打开 RDC 文件后，在 Python Shell 中执行：
    exec(open(r'd:\Code\git\renderdoc\scripts\rdc_analyzer\export_textures_rdoc.py').read())

这将自动导出当前捕获的所有纹理到 RDC 文件同目录的 <capture_name>_textures 文件夹。
"""

import os
import sys
import json
from pathlib import Path

print("=" * 60)
print("RenderDoc Texture Exporter")
print("=" * 60)

# 检查是否在 RenderDoc 环境中
try:
    ctx = pyrenderdoc.GetCaptureContext()
    if ctx is None:
        print("[ERROR] No capture context available.")
        print("Please open an RDC file first!")
        raise SystemExit
    
    # 获取当前打开的文件路径
    cap_file = ctx.GetCaptureFilename()
    if not cap_file:
        print("[ERROR] Cannot get capture filename.")
        raise SystemExit
    
    print(f"[INFO] Capture: {cap_file}")
    
    # 设置输出目录
    cap_path = Path(cap_file)
    output_dir = cap_path.parent / f"{cap_path.stem}_textures"
    output_dir.mkdir(exist_ok=True)
    print(f"[INFO] Output directory: {output_dir}")
    
    # 获取 ReplayController
    controller = ctx.GetReplay().GetController()
    if not controller:
        print("[ERROR] Cannot get replay controller.")
        raise SystemExit
    
    # 获取所有纹理
    textures = controller.GetTextures()
    print(f"[INFO] Found {len(textures)} textures")
    
    # 导出配置
    MAX_THUMBNAIL_SIZE = 256
    exported = []
    failed = []
    
    for i, tex in enumerate(textures):
        # 跳过内部纹理
        if tex.resourceId == renderdoc.ResourceId.Null():
            continue
        
        res_id = int(tex.resourceId)
        filename = f"tex_{res_id}.png"
        filepath = output_dir / filename
        
        try:
            # 设置保存参数
            save = renderdoc.TextureSave()
            save.resourceId = tex.resourceId
            save.destType = renderdoc.FileType.PNG
            save.mip = 0
            save.slice.sliceIndex = 0
            
            # 计算缩略图尺寸
            width, height = tex.width, tex.height
            if width > MAX_THUMBNAIL_SIZE or height > MAX_THUMBNAIL_SIZE:
                scale = MAX_THUMBNAIL_SIZE / max(width, height)
                width = int(width * scale)
                height = int(height * scale)
            
            # 保存纹理
            controller.SaveTexture(save, str(filepath))
            
            exported.append({
                "resource_id": res_id,
                "filename": filename,
                "width": tex.width,
                "height": tex.height,
                "format": str(tex.format.Name()),
                "mips": tex.mips,
                "arraysize": tex.arraysize
            })
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(textures)}")
                
        except Exception as e:
            failed.append({"resource_id": res_id, "error": str(e)})
    
    # 保存清单文件
    manifest = {
        "capture_file": str(cap_file),
        "total_textures": len(textures),
        "exported_count": len(exported),
        "failed_count": len(failed),
        "textures": exported
    }
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print(f"[DONE] Exported {len(exported)} textures")
    if failed:
        print(f"[WARN] Failed to export {len(failed)} textures")
    print(f"[INFO] Manifest saved to: {manifest_path}")
    print()
    print("Next step: Run analyze_rdc.py to generate report with thumbnails")
    print("=" * 60)

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
        print("     exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\export_textures_rdoc.py').read())")
    else:
        raise
