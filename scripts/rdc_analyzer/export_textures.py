#!/usr/bin/env python3
"""
RDC 纹理导出工具

从 RenderDoc 捕获文件中导出所有纹理为 PNG 缩略图。
需要在具有兼容 GPU 的环境中运行（需要 RenderDoc 回放支持）。

用法:
    # 方式 1: 在 RenderDoc Python Shell 中运行
    exec(open('export_textures.py').read())
    export_textures_from_capture(pyrenderdoc.GetCaptureContext())
    
    # 方式 2: 命令行（需要 renderdoc 模块可用）
    python export_textures.py <rdc_file> -o output/textures/

依赖:
    - RenderDoc Python API (renderdoc 模块)
    - 兼容的 GPU 环境用于回放

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False
    print("[WARNING] renderdoc module not available. Some features may not work.")


class TextureExporter:
    """纹理导出器类"""
    
    # 最大缩略图尺寸
    MAX_THUMBNAIL_SIZE = 256
    
    def __init__(self, output_dir: str = "textures"):
        """初始化导出器
        
        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.exported_textures: List[Dict[str, Any]] = []
    
    def export_from_controller(
        self,
        controller: 'rd.ReplayController',
        max_textures: int = -1,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """从 ReplayController 导出所有纹理
        
        Args:
            controller: RenderDoc ReplayController 实例
            max_textures: 最大导出数量，-1 表示全部
            verbose: 是否输出详细信息
        
        Returns:
            导出的纹理信息列表
        """
        if not HAS_RENDERDOC:
            raise RuntimeError("renderdoc module not available")
        
        textures = controller.GetTextures()
        total = len(textures)
        
        if verbose:
            print(f"[TextureExporter] Found {total} textures")
        
        count = 0
        for i, tex_desc in enumerate(textures):
            if max_textures > 0 and count >= max_textures:
                break
            
            # 跳过无效纹理
            if tex_desc.resourceId == rd.ResourceId.Null():
                continue
            
            # 获取纹理信息
            res_id = tex_desc.resourceId
            width = tex_desc.width
            height = tex_desc.height
            depth = tex_desc.depth
            fmt = tex_desc.format
            
            if verbose:
                print(f"  [{i+1}/{total}] Exporting texture {res_id}: {width}x{height} {fmt.Name()}")
            
            # 构建输出文件名
            filename = f"tex_{res_id}_{width}x{height}.png"
            output_path = self.output_dir / filename
            
            # 配置导出参数
            save_data = rd.TextureSave()
            save_data.resourceId = res_id
            save_data.destType = rd.FileType.PNG
            save_data.mip = 0  # 只导出 mip 0
            save_data.alpha = rd.AlphaMapping.Preserve
            
            # 对于大纹理，可以考虑降采样（但 API 不直接支持）
            # 这里我们导出原始尺寸的 mip 0
            
            try:
                result = controller.SaveTexture(save_data, str(output_path))
                
                if result == rd.ResultCode.Succeeded:
                    self.exported_textures.append({
                        "resource_id": int(res_id),
                        "filename": filename,
                        "width": width,
                        "height": height,
                        "depth": depth,
                        "format": fmt.Name(),
                        "path": str(output_path)
                    })
                    count += 1
                else:
                    if verbose:
                        print(f"    [WARN] Failed to save: {result}")
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] Exception: {e}")
        
        if verbose:
            print(f"[TextureExporter] Exported {count} textures to {self.output_dir}")
        
        return self.exported_textures
    
    def save_manifest(self, manifest_path: Optional[str] = None) -> str:
        """保存导出清单文件
        
        Args:
            manifest_path: 清单文件路径，默认为 output_dir/manifest.json
        
        Returns:
            清单文件路径
        """
        if manifest_path is None:
            manifest_path = str(self.output_dir / "manifest.json")
        
        manifest = {
            "version": "1.0",
            "output_dir": str(self.output_dir),
            "texture_count": len(self.exported_textures),
            "textures": self.exported_textures
        }
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path


def export_textures_from_rdc(
    rdc_path: str,
    output_dir: str = "textures",
    max_textures: int = -1,
    verbose: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """从 RDC 文件导出纹理（独立模式）
    
    此函数会打开 RDC 文件，创建 ReplayController，然后导出纹理。
    需要在具有兼容 GPU 的环境中运行。
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录
        max_textures: 最大导出数量
        verbose: 详细输出
    
    Returns:
        导出的纹理列表，失败返回 None
    """
    if not HAS_RENDERDOC:
        print("[ERROR] renderdoc module not available")
        return None
    
    if not os.path.exists(rdc_path):
        print(f"[ERROR] File not found: {rdc_path}")
        return None
    
    print(f"[TextureExporter] Opening capture: {rdc_path}")
    
    # 打开捕获文件
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, '', None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to open capture: {status}")
        cap.Shutdown()
        return None
    
    # 检查是否需要远程服务器
    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        print("[ERROR] Local replay not supported. Need compatible GPU.")
        cap.Shutdown()
        return None
    
    # 创建回放控制器
    print("[TextureExporter] Creating replay controller...")
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to create replay controller: {status}")
        cap.Shutdown()
        return None
    
    try:
        # 导出纹理
        exporter = TextureExporter(output_dir)
        results = exporter.export_from_controller(controller, max_textures, verbose)
        
        # 保存清单
        manifest_path = exporter.save_manifest()
        print(f"[TextureExporter] Manifest saved to: {manifest_path}")
        
        return results
    finally:
        controller.Shutdown()
        cap.Shutdown()


def export_textures_from_capture(ctx: 'pyrenderdoc.CaptureContext') -> Optional[List[Dict[str, Any]]]:
    """从 RenderDoc UI 上下文导出纹理（UI 模式）
    
    在 RenderDoc 的 Python Shell 中调用此函数。
    
    用法（在 RenderDoc Python Shell 中）:
        import sys
        sys.path.insert(0, r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer')
        from export_textures import export_textures_from_capture
        export_textures_from_capture(pyrenderdoc.GetCaptureContext())
    
    Args:
        ctx: RenderDoc CaptureContext (pyrenderdoc.GetCaptureContext())
    
    Returns:
        导出的纹理列表
    """
    if not ctx.IsCaptureLoaded():
        print("[ERROR] No capture loaded")
        return None
    
    # 获取回放控制器
    controller = ctx.Replay().GetReplay()
    if controller is None:
        print("[ERROR] No replay controller available")
        return None
    
    # 构建输出目录
    capture_path = ctx.GetCaptureFilename()
    capture_name = Path(capture_path).stem
    output_dir = Path(capture_path).parent / f"{capture_name}_textures"
    
    print(f"[TextureExporter] Exporting to: {output_dir}")
    
    exporter = TextureExporter(str(output_dir))
    results = exporter.export_from_controller(controller, verbose=True)
    
    manifest_path = exporter.save_manifest()
    print(f"[TextureExporter] Manifest saved to: {manifest_path}")
    
    return results


def generate_html_gallery(manifest_path: str, output_html: str = "texture_gallery.html"):
    """从清单文件生成 HTML 图库预览
    
    Args:
        manifest_path: 清单文件路径
        output_html: 输出 HTML 文件路径
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    textures = manifest.get("textures", [])
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Texture Gallery</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #e8e8e8;
            padding: 24px;
            margin: 0;
        }
        h1 {
            color: #a78bfa;
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 16px;
        }
        .texture-card {
            background: #1f2940;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .texture-card img {
            width: 100%;
            height: 150px;
            object-fit: contain;
            background: #000;
        }
        .texture-info {
            padding: 12px;
            font-size: 0.85rem;
        }
        .texture-id {
            color: #7c3aed;
            font-weight: 600;
        }
        .texture-dims {
            color: #94a3b8;
        }
    </style>
</head>
<body>
    <h1>🖼️ Texture Gallery</h1>
    <p>Total: """ + str(len(textures)) + """ textures</p>
    <div class="gallery">
"""
    
    for tex in textures:
        html += f"""
        <div class="texture-card">
            <img src="{tex['filename']}" alt="{tex['filename']}" loading="lazy">
            <div class="texture-info">
                <div class="texture-id">ID: {tex['resource_id']}</div>
                <div class="texture-dims">{tex['width']}×{tex['height']}</div>
                <div class="texture-dims">{tex['format']}</div>
            </div>
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    output_path = Path(manifest_path).parent / output_html
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[Gallery] Generated: {output_path}")
    return str(output_path)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="Export textures from RDC capture files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all textures from a capture
  python export_textures.py capture.rdc -o textures/
  
  # Export only first 10 textures
  python export_textures.py capture.rdc -o textures/ --max 10
  
  # Generate gallery from existing manifest
  python export_textures.py --gallery textures/manifest.json

Note:
  This script requires a compatible GPU for replay.
  For headless usage, consider using a GPU-enabled server.
"""
    )
    
    parser.add_argument(
        "input",
        nargs="?",
        help="RDC file path or manifest.json path (with --gallery)"
    )
    parser.add_argument(
        "-o", "--output",
        default="textures",
        help="Output directory for exported textures (default: textures)"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=-1,
        help="Maximum number of textures to export (-1 for all)"
    )
    parser.add_argument(
        "--gallery",
        action="store_true",
        help="Generate HTML gallery from manifest.json"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (less output)"
    )
    
    args = parser.parse_args()
    
    if not args.input:
        parser.print_help()
        return 1
    
    if args.gallery:
        # 从清单生成图库
        if not os.path.exists(args.input):
            print(f"[ERROR] Manifest not found: {args.input}")
            return 1
        generate_html_gallery(args.input)
        return 0
    
    # 导出纹理
    if not HAS_RENDERDOC:
        print("""
[ERROR] RenderDoc Python module not available.

To use this script, you need to:
1. Run it inside RenderDoc's Python Shell, OR
2. Set up the renderdoc Python module in your environment

For option 1, open RenderDoc, load a capture, then in Python Shell:
    exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\export_textures.py').read())
    export_textures_from_capture(pyrenderdoc.GetCaptureContext())

For option 2, you need to build RenderDoc with Python bindings and
add the module to your PYTHONPATH.
""")
        return 1
    
    results = export_textures_from_rdc(
        args.input,
        args.output,
        args.max,
        verbose=not args.quiet
    )
    
    if results is None:
        return 1
    
    # 自动生成图库
    manifest_path = Path(args.output) / "manifest.json"
    if manifest_path.exists():
        generate_html_gallery(str(manifest_path))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
