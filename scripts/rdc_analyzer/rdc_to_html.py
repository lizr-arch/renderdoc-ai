#!/usr/bin/env python3
"""
RDC 一键分析工具 - 从 .rdc 文件直接生成离线 HTML 报告

此脚本整合了 export_textures.py 和 generate_offline_report.py，
实现从 RDC 捕获文件一键生成可离线浏览的纹理分析报告。

用法:
    # 方式 1: 命令行模式 (需要 renderdoc 模块 + 兼容 GPU)
    python rdc_to_html.py capture.rdc -o report.html
    
    # 方式 2: 在 RenderDoc Python Shell 中运行
    exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\rdc_to_html.py').read())
    rdc_to_html_from_context(pyrenderdoc)

依赖:
    - renderdoc Python 模块 (编译 RenderDoc 后生成，或在 RenderDoc UI 中使用)
    - 兼容 GPU 用于回放捕获

Author: RenderDoc Texture Analyzer
Version: 1.0.0
"""

import os
import sys
import json
import shutil
import tempfile
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# 导入去重检测器
try:
    from core.duplicate_detector import detect_duplicates_from_texture_list, DuplicateDetector
    HAS_DUPLICATE_DETECTOR = True
except ImportError:
    HAS_DUPLICATE_DETECTOR = False

# 导入热度分析器
try:
    from core.texture_usage_analyzer import TextureUsageAnalyzer, analyze_texture_usage
    HAS_USAGE_ANALYZER = True
except ImportError:
    HAS_USAGE_ANALYZER = False

# 检测 renderdoc 模块
HAS_RENDERDOC = False
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    pass

# 检测是否在 RenderDoc UI 环境中
IN_RENDERDOC_UI = 'pyrenderdoc' in dir() or 'qrenderdoc' in sys.modules


def print_no_renderdoc_help():
    """当 renderdoc 模块不可用时，打印帮助信息"""
    script_path = Path(__file__).resolve()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    renderdoc 模块不可用                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

要使用此工具直接从 .rdc 文件生成报告，您需要 renderdoc Python 模块。
以下是几种解决方案：

┌──────────────────────────────────────────────────────────────────────────────┐
│ 方式 1: 在 RenderDoc UI 中运行 (推荐 - 无需编译)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  1. 打开 RenderDoc 应用程序                                                   │
│  2. 加载您的 .rdc 捕获文件                                                    │
│  3. 打开 Python Shell: Window → Python Shell                                 │
│  4. 在 Shell 中执行以下代码:                                                  │
│                                                                              │
│     exec(open(r'""" + str(script_path) + """').read())
│     rdc_to_html_from_context(pyrenderdoc)                                    │
│                                                                              │
│  报告将保存在 .rdc 文件同目录下。                                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 方式 2: 使用已手动导出的纹理                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  如果您已在 RenderDoc 中手动导出了纹理 (Texture Viewer → Save All):           │
│                                                                              │
│     python generate_offline_report.py <rdc_path> -o report.html              │
│                                                                              │
│  脚本会自动查找 <rdc_name>_textures/textures.json 文件。                      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 方式 3: 编译 RenderDoc 获取 Python 模块                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  1. 按照 docs/CONTRIBUTING/Compiling.md 编译 RenderDoc                        │
│  2. 将生成的 renderdoc.pyd 添加到 PYTHONPATH                                  │
│  3. 然后可以使用命令行模式:                                                   │
│                                                                              │
│     python rdc_to_html.py capture.rdc -o report.html                         │
└──────────────────────────────────────────────────────────────────────────────┘
""")


class RdcToHtmlConverter:
    """RDC 到 HTML 转换器"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.temp_dir: Optional[Path] = None
        
    def log(self, msg: str):
        if self.verbose:
            print(f"[rdc_to_html] {msg}")
    
    def export_textures_from_controller(
        self, 
        controller: 'rd.ReplayController',
        output_dir: Path
    ) -> Tuple[int, Path]:
        """
        从 ReplayController 导出所有纹理
        
        Returns:
            (导出数量, manifest.json 路径)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        textures = controller.GetTextures()
        self.log(f"Found {len(textures)} textures in capture")
        
        exported = []
        for i, tex_desc in enumerate(textures):
            # 跳过无效纹理
            if tex_desc.resourceId == rd.ResourceId.Null():
                continue
            
            res_id = int(tex_desc.resourceId)
            width = tex_desc.width
            height = tex_desc.height
            depth = tex_desc.depth
            mips = tex_desc.mips
            array_size = tex_desc.arraysize
            fmt_name = tex_desc.format.Name()
            
            # 获取资源名称
            res_name = ""
            try:
                resources = controller.GetResources()
                for r in resources:
                    if r.resourceId == tex_desc.resourceId:
                        res_name = r.name
                        break
            except:
                pass
            
            # 构建文件名
            filename = f"tex_{res_id}_{width}x{height}.png"
            output_path = output_dir / filename
            
            # 配置导出参数
            save_data = rd.TextureSave()
            save_data.resourceId = tex_desc.resourceId
            save_data.destType = rd.FileType.PNG
            save_data.mip = 0
            save_data.slice.sliceIndex = 0
            save_data.alpha = rd.AlphaMapping.Preserve
            
            try:
                result = controller.SaveTexture(save_data, str(output_path))
                
                if result == rd.ResultCode.Succeeded:
                    exported.append({
                        "id": res_id,
                        "name": res_name,
                        "filename": filename,
                        "width": width,
                        "height": height,
                        "depth": depth,
                        "mips": mips,
                        "arrayLayers": array_size,
                        "format": fmt_name
                    })
                    
                    if self.verbose and (len(exported) % 50 == 0 or len(exported) <= 5):
                        self.log(f"  Exported {len(exported)}/{len(textures)}: {filename}")
            except Exception as e:
                if self.verbose:
                    self.log(f"  [WARN] Failed to export texture {res_id}: {e}")
        
        # 保存 manifest
        manifest_path = output_dir / "textures.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump({"textures": exported}, f, indent=2, ensure_ascii=False)
        
        self.log(f"Exported {len(exported)} textures to {output_dir}")
        return len(exported), manifest_path
    
    def convert_rdc_file(
        self,
        rdc_path: str,
        output_html: Optional[str] = None,
        keep_temp: bool = False
    ) -> Optional[str]:
        """
        从 RDC 文件生成 HTML 报告 (命令行模式)
        
        Args:
            rdc_path: RDC 文件路径
            output_html: 输出 HTML 路径，默认为 <rdc_name>_report.html
            keep_temp: 是否保留临时目录
        
        Returns:
            生成的 HTML 文件路径，失败返回 None
        """
        if not HAS_RENDERDOC:
            print_no_renderdoc_help()
            return None
        
        rdc_path = Path(rdc_path).resolve()
        if not rdc_path.exists():
            self.log(f"[ERROR] File not found: {rdc_path}")
            return None
        
        # 确定输出路径
        if output_html is None:
            output_html = rdc_path.parent / f"{rdc_path.stem}_report.html"
        else:
            output_html = Path(output_html).resolve()
        
        self.log(f"Converting: {rdc_path}")
        self.log(f"Output: {output_html}")
        
        # 初始化 RenderDoc
        rd.InitialiseReplay(rd.GlobalEnvironment(), [])
        
        try:
            # 打开捕获文件
            cap = rd.OpenCaptureFile()
            status = cap.OpenFile(str(rdc_path), '', None)
            
            if status != rd.ResultCode.Succeeded:
                self.log(f"[ERROR] Failed to open capture: {status}")
                return None
            
            # 检查回放支持
            if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
                self.log("[ERROR] Local replay not supported. Need compatible GPU.")
                cap.Shutdown()
                return None
            
            # 创建回放控制器
            self.log("Creating replay controller (this may take a moment)...")
            status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
            
            if status != rd.ResultCode.Succeeded:
                self.log(f"[ERROR] Failed to create replay: {status}")
                cap.Shutdown()
                return None
            
            try:
                # 创建临时目录
                self.temp_dir = Path(tempfile.mkdtemp(prefix="rdc_textures_"))
                self.log(f"Using temp directory: {self.temp_dir}")
                
                # 导出纹理
                count, manifest_path = self.export_textures_from_controller(
                    controller, self.temp_dir
                )
                
                if count == 0:
                    self.log("[WARN] No textures exported")
                
                # 运行去重检测（需要 controller）
                duplicate_analysis = self._run_duplicate_detection(controller)
                
                # 运行热度分析（需要 controller）
                usage_analysis = self._run_usage_analysis(controller)
                
                # 生成 HTML 报告
                html_path = self._generate_html_report(
                    rdc_path, manifest_path, output_html, 
                    duplicate_analysis, usage_analysis
                )
                
                return html_path
                
            finally:
                controller.Shutdown()
                cap.Shutdown()
                
                # 清理临时目录
                if not keep_temp and self.temp_dir and self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    self.log("Cleaned up temp directory")
                elif keep_temp:
                    self.log(f"Temp directory kept at: {self.temp_dir}")
        
        finally:
            rd.ShutdownReplay()
    
    def convert_from_context(
        self,
        ctx: 'pyrenderdoc.CaptureContext',
        output_html: Optional[str] = None
    ) -> Optional[str]:
        """
        从 RenderDoc UI 上下文生成 HTML 报告 (UI 模式)
        
        Args:
            ctx: RenderDoc CaptureContext (pyrenderdoc.GetCaptureContext())
            output_html: 输出 HTML 路径
        
        Returns:
            生成的 HTML 文件路径
        """
        if not ctx.IsCaptureLoaded():
            self.log("[ERROR] No capture loaded in RenderDoc")
            return None
        
        # 获取捕获文件路径
        rdc_path = Path(ctx.GetCaptureFilename())
        self.log(f"Processing: {rdc_path.name}")
        
        # 确定输出路径
        if output_html is None:
            output_html = rdc_path.parent / f"{rdc_path.stem}_report.html"
        else:
            output_html = Path(output_html)
        
        # 创建临时目录
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rdc_textures_"))
        
        def do_export(controller):
            """在 replay 线程中执行导出"""
            count, manifest_path = self.export_textures_from_controller(
                controller, self.temp_dir
            )
            return manifest_path
        
        # 在 replay 线程中执行
        manifest_path = ctx.Replay().BlockInvoke(do_export)
        
        # 生成 HTML
        html_path = self._generate_html_report(rdc_path, manifest_path, output_html)
        
        # 清理
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        
        return html_path
    
    def _run_duplicate_detection(
        self,
        controller: 'rd.ReplayController'
    ) -> Optional[dict]:
        """
        运行纹理去重检测
        
        Args:
            controller: RenderDoc ReplayController
            
        Returns:
            去重分析结果字典，失败返回 None
        """
        if not HAS_DUPLICATE_DETECTOR:
            self.log("[INFO] Duplicate detector not available, skipping")
            return None
        
        try:
            self.log("Running duplicate detection...")
            detector = DuplicateDetector(controller, verbose=self.verbose)
            result = detector.detect()
            
            if result:
                self.log(f"  Found {len(result.duplicate_groups)} duplicate groups")
                self.log(f"  Total wasted VRAM: {result.total_wasted_bytes / 1024 / 1024:.2f} MB")
                return result.to_dict()
            else:
                self.log("  No duplicates found")
                return None
                
        except Exception as e:
            self.log(f"[WARN] Duplicate detection failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _run_usage_analysis(
        self,
        controller: 'rd.ReplayController'
    ) -> Optional[dict]:
        """
        运行纹理热度分析
        
        Args:
            controller: RenderDoc ReplayController
            
        Returns:
            使用分析结果字典，失败返回 None
        """
        if not HAS_USAGE_ANALYZER:
            self.log("[INFO] Usage analyzer not available, skipping")
            return None
        
        try:
            self.log("Running texture usage analysis...")
            analyzer = TextureUsageAnalyzer(controller, verbose=self.verbose)
            result = analyzer.analyze()
            
            if result:
                self.log(f"  Used: {result.used_textures}, Unused: {result.unused_textures}")
                if result.hot_list:
                    top = result.hot_list[0]
                    self.log(f"  Hottest: {top.name or top.resource_id} ({top.use_count} uses)")
                return result.to_dict()
            else:
                self.log("  No usage data")
                return None
                
        except Exception as e:
            self.log(f"[WARN] Usage analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_html_report(
        self,
        rdc_path: Path,
        manifest_path: Path,
        output_html: Path,
        duplicate_analysis: Optional[dict] = None,
        usage_analysis: Optional[dict] = None
    ) -> Optional[str]:
        """调用 generate_offline_report 生成 HTML"""
        
        # 导入生成器模块
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        
        try:
            from generate_offline_report import (
                load_textures_from_export,
                generate_offline_html
            )
            
            # 由于 load_textures_from_export 期望 rdc 路径，
            # 我们需要构造一个兼容的调用方式
            # 直接读取 manifest
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            textures = []
            textures_dir = manifest_path.parent
            tex_list = manifest.get("textures", [])
            
            import base64
            
            for tex in tex_list:
                filename = tex.get("filename")
                thumbnail_data = ""
                
                if filename:
                    full_path = textures_dir / filename
                    if full_path.exists():
                        with open(full_path, 'rb') as img_file:
                            b64_data = base64.b64encode(img_file.read()).decode('utf-8')
                            thumbnail_data = f"data:image/png;base64,{b64_data}"
                
                textures.append({
                    "id": tex.get("id"),
                    "name": tex.get("name", ""),
                    "width": tex.get("width", 0),
                    "height": tex.get("height", 0),
                    "depth": tex.get("depth", 1),
                    "format": tex.get("format", "UNKNOWN"),
                    "mips": tex.get("mips", 1),
                    "arrayLayers": tex.get("arrayLayers", 1),
                    "thumbnail": thumbnail_data,
                    "channels": {}  # 通道分离需要 PIL，这里简化处理
                })
            
            # 生成 HTML（传递分析结果）
            generate_offline_html(
                textures, 
                rdc_path.name, 
                str(output_html),
                duplicate_analysis=duplicate_analysis,
                usage_analysis=usage_analysis
            )
            
            self.log(f"✅ Report generated: {output_html}")
            return str(output_html)
            
        except ImportError as e:
            self.log(f"[ERROR] Failed to import generate_offline_report: {e}")
            return None
        except Exception as e:
            self.log(f"[ERROR] Failed to generate HTML: {e}")
            import traceback
            traceback.print_exc()
            return None


# ============================================================================
# 便捷函数 - 供 RenderDoc Shell 调用
# ============================================================================

def rdc_to_html(rdc_path: str, output_html: Optional[str] = None) -> Optional[str]:
    """
    一键从 RDC 文件生成 HTML 报告 (命令行模式)
    
    用法:
        rdc_to_html("capture.rdc")
        rdc_to_html("capture.rdc", "my_report.html")
    """
    converter = RdcToHtmlConverter(verbose=True)
    return converter.convert_rdc_file(rdc_path, output_html)


def rdc_to_html_from_context(pyrenderdoc_module, output_html: Optional[str] = None) -> Optional[str]:
    """
    从 RenderDoc UI 上下文生成 HTML 报告
    
    用法 (在 RenderDoc Python Shell 中):
        exec(open(r'path/to/rdc_to_html.py').read())
        rdc_to_html_from_context(pyrenderdoc)
    """
    ctx = pyrenderdoc_module.GetCaptureContext()
    converter = RdcToHtmlConverter(verbose=True)
    return converter.convert_from_context(ctx, output_html)


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RDC 一键分析工具 - 从 .rdc 文件生成离线 HTML 报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成报告 (输出到同目录)
  python rdc_to_html.py capture.rdc
  
  # 指定输出路径
  python rdc_to_html.py capture.rdc -o my_report.html
  
  # 保留临时文件 (调试用)
  python rdc_to_html.py capture.rdc --keep-temp

在 RenderDoc Python Shell 中使用:
  exec(open(r'd:\\path\\to\\rdc_to_html.py').read())
  rdc_to_html_from_context(pyrenderdoc)
"""
    )
    
    parser.add_argument(
        "rdc_path",
        nargs="?",
        help="RDC 捕获文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出 HTML 文件路径 (默认: <rdc_name>_report.html)"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时导出目录 (调试用)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="安静模式"
    )
    
    args = parser.parse_args()
    
    # 检查是否有 renderdoc 模块
    if not HAS_RENDERDOC:
        print_no_renderdoc_help()
        return 1
    
    if not args.rdc_path:
        parser.print_help()
        return 1
    
    # 执行转换
    converter = RdcToHtmlConverter(verbose=not args.quiet)
    result = converter.convert_rdc_file(
        args.rdc_path,
        args.output,
        keep_temp=args.keep_temp
    )
    
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
