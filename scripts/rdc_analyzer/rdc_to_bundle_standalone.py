#!/usr/bin/env python3
"""
RDC → 4 页面分析报告 全自动生成器（独立运行版）

此脚本使用 renderdoc.pyd 模块直接加载 RDC 文件并生成报告，
无需打开 RenderDoc GUI。

用法:
    py -3 rdc_to_bundle_standalone.py <rdc_file> [output_dir]

示例:
    py -3 rdc_to_bundle_standalone.py D:\backup\dayuanjing.rdc
    py -3 rdc_to_bundle_standalone.py D:\backup\dayuanjing.rdc D:\reports\output

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import os
import sys
import json
import base64
import tempfile
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# ============================================================================
# 配置 RenderDoc 模块路径
# ============================================================================

# RenderDoc Development 构建路径
RENDERDOC_DEV_PATH = Path(r'D:\Code\git\renderdoc\x64\Development')
PYMODULES_PATH = RENDERDOC_DEV_PATH / 'pymodules'

# 确保 DLL 可被找到 (Python 3.8+ 需要显式添加)
dll_path = str(RENDERDOC_DEV_PATH)
os.environ["PATH"] = dll_path + os.pathsep + os.environ.get("PATH", "")
if sys.version_info >= (3, 8):
    os.add_dll_directory(dll_path)

# 添加 pymodules 到搜索路径
sys.path.insert(0, str(PYMODULES_PATH))

# 脚本目录（用于导入 report_bundle_generator）
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================================
# 导入 RenderDoc 模块
# ============================================================================

print("=" * 70)
print("RDC → 4 Page Report Generator (Standalone)")
print("=" * 70)

try:
    import renderdoc as rd
    print(f"[OK] Loaded renderdoc module")
except ImportError as e:
    print(f"[ERROR] Failed to import renderdoc: {e}")
    print(f"  Expected path: {PYMODULES_PATH}")
    print(f"  DLL path: {RENDERDOC_DEV_PATH}")
    sys.exit(1)

# ============================================================================
# 参数解析
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate HTML report bundle from RDC capture file'
    )
    parser.add_argument('rdc_file', help='Path to .rdc capture file')
    parser.add_argument('output_dir', nargs='?', default=None,
                        help='Output directory (default: <rdc_name>_report)')
    parser.add_argument('--max-events', type=int, default=2000,
                        help='Maximum events to process (default: 2000)')
    parser.add_argument('--max-textures', type=int, default=500,
                        help='Maximum textures to extract thumbnails (default: 500)')
    parser.add_argument('--export-rt', action='store_true',
                        help='Export RT snapshots for all draw events')
    parser.add_argument('--rt-max-size', type=int, default=256,
                        help='Maximum RT thumbnail size (default: 256)')
    parser.add_argument('--rt-skip-interval', type=int, default=1,
                        help='Export every N-th draw event (default: 1 = all)')
    return parser.parse_args()

# ============================================================================
# 主逻辑
# ============================================================================

THUMBNAIL_MAX_SIZE = 128

def flatten_actions(actions, depth=0):
    """递归展平 action 层级结构"""
    result = []
    for action in actions:
        result.append((action, depth))
        if action.children:
            result.extend(flatten_actions(action.children, depth + 1))
    return result


def get_action_name(action):
    """获取 action 的显示名称"""
    if action.customName:
        return str(action.customName)
    # 使用 flags 判断类型
    flags = action.flags
    if flags & rd.ActionFlags.Drawcall:
        return f"Draw ({action.numIndices} indices)"
    elif flags & rd.ActionFlags.Dispatch:
        return f"Dispatch ({action.dispatchDimension[0]}x{action.dispatchDimension[1]}x{action.dispatchDimension[2]})"
    elif flags & rd.ActionFlags.Clear:
        return "Clear"
    elif flags & rd.ActionFlags.PassBoundary:
        return "RenderPass Boundary"
    else:
        return f"Event #{action.eventId}"


def main():
    args = parse_args()
    
    rdc_path = Path(args.rdc_file)
    if not rdc_path.exists():
        print(f"[ERROR] RDC file not found: {rdc_path}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir) if args.output_dir else rdc_path.parent / f"{rdc_path.stem}_report"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] Input:  {rdc_path}")
    print(f"[INFO] Output: {output_dir}")
    print()
    
    # ========================================================================
    # 初始化 RenderDoc Replay API
    # ========================================================================
    
    print("[1/6] Initializing RenderDoc Replay API...")
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    
    # ========================================================================
    # 打开 Capture 文件
    # ========================================================================
    
    print("[2/6] Opening capture file...")
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(str(rdc_path), '', None)
    
    if result != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to open capture: {result}")
        rd.ShutdownReplay()
        sys.exit(1)
    
    if not cap.LocalReplaySupport():
        print("[ERROR] Capture cannot be replayed on this system")
        cap.Shutdown()
        rd.ShutdownReplay()
        sys.exit(1)
    
    # ========================================================================
    # 初始化 Replay Controller
    # ========================================================================
    
    print("[3/6] Initializing replay (this may take a while for large captures)...")
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if result != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to initialize replay: {result}")
        cap.Shutdown()
        rd.ShutdownReplay()
        sys.exit(1)
    
    print(f"  Replay initialized successfully!")
    
    # ========================================================================
    # 提取数据
    # ========================================================================
    
    # 获取 API 类型
    api_props = controller.GetAPIProperties()
    api_name = str(api_props.pipelineType).replace('GraphicsAPI.', '')
    
    # 获取根 Actions
    root_actions = controller.GetRootActions()
    all_actions = flatten_actions(root_actions)
    print(f"  Total events: {len(all_actions)}")
    
    # 获取纹理列表
    textures_desc = controller.GetTextures()
    print(f"  Total textures: {len(textures_desc)}")
    
    # ------------------------------------------------------------------------
    # 提取纹理信息和缩略图
    # ------------------------------------------------------------------------
    
    print("[4/6] Extracting textures and thumbnails...")
    temp_dir = Path(tempfile.mkdtemp(prefix="rdoc_bundle_"))
    textures_data = []
    total_vram = 0
    
    for i, tex in enumerate(textures_desc[:args.max_textures]):
        if tex.resourceId == rd.ResourceId.Null():
            continue
        
        res_id = int(tex.resourceId)
        width = tex.width
        height = tex.height
        depth = tex.depth
        fmt_name = tex.format.Name()
        
        # 估算 VRAM 大小
        bpp = 4
        fmt_lower = fmt_name.lower()
        if any(x in fmt_lower for x in ['bc', 'dxt', 'etc', 'astc']):
            bpp = 1
        elif 'r8' in fmt_lower and 'g8' not in fmt_lower:
            bpp = 1
        elif 'r16' in fmt_lower or 'r8g8' in fmt_lower:
            bpp = 2
        elif 'rgba16' in fmt_lower or 'r32' in fmt_lower:
            bpp = 8
        elif 'rgba32' in fmt_lower:
            bpp = 16
        
        estimated_size = width * height * depth * bpp
        if tex.mips > 1:
            estimated_size = int(estimated_size * 1.33)
        if tex.arraysize > 1:
            estimated_size *= tex.arraysize
        
        total_vram += estimated_size
        
        # 简化格式名称
        simple_format = fmt_name
        for prefix in ['VK_FORMAT_', 'DXGI_FORMAT_', 'GL_']:
            if simple_format.startswith(prefix):
                simple_format = simple_format[len(prefix):]
        
        # 生成缩略图
        thumbnail_b64 = ""
        try:
            thumb_path = temp_dir / f"tex_{res_id}.png"
            # 计算缩略图尺寸
            scale = min(THUMBNAIL_MAX_SIZE / max(width, 1), THUMBNAIL_MAX_SIZE / max(height, 1), 1.0)
            thumb_w = max(1, int(width * scale))
            thumb_h = max(1, int(height * scale))
            
            save_result = controller.SaveTexture(
                rd.TextureSave({
                    'resourceId': tex.resourceId,
                    'destType': rd.FileType.PNG,
                    'slice': rd.TextureSliceSaveData({'sliceIndex': 0}),
                    'mip': 0,
                }),
                str(thumb_path)
            )
            
            if save_result and thumb_path.exists():
                with open(thumb_path, 'rb') as f:
                    thumbnail_b64 = base64.b64encode(f.read()).decode('ascii')
        except Exception as e:
            pass  # 缩略图失败不影响流程
        
        tex_info = {
            "id": res_id,
            "name": f"#tex_{res_id} ({width}×{height})",
            "width": width,
            "height": height,
            "depth": depth,
            "format": simple_format,
            "mips": tex.mips,
            "arraySize": tex.arraysize,
            "msaa": tex.msSamp,
            "estimatedSize": estimated_size,
            "thumbnail": thumbnail_b64
        }
        textures_data.append(tex_info)
        
        if (i + 1) % 50 == 0:
            print(f"    Processed {i + 1}/{min(len(textures_desc), args.max_textures)} textures...")
    
    print(f"  Extracted {len(textures_data)} textures, total VRAM: {total_vram / (1024*1024):.1f} MB")
    
    # ------------------------------------------------------------------------
    # 提取事件信息
    # ------------------------------------------------------------------------
    
    print("[5/6] Extracting events...")
    events_data = []
    
    for i, (action, depth) in enumerate(all_actions[:args.max_events]):
        # 判断事件类型
        flags = int(action.flags)
        if flags & rd.ActionFlags.Drawcall:
            event_type = "draw"
        elif flags & rd.ActionFlags.Dispatch:
            event_type = "dispatch"
        elif flags & rd.ActionFlags.Clear:
            event_type = "clear"
        elif flags & rd.ActionFlags.Copy:
            event_type = "copy"
        elif flags & rd.ActionFlags.PushMarker:
            event_type = "marker_push"
        elif flags & rd.ActionFlags.PopMarker:
            event_type = "marker_pop"
        else:
            event_type = "other"
        
        # 检查是否有子事件
        has_children = len(action.children) > 0 if hasattr(action, 'children') else False
        child_count = len(action.children) if has_children else 0
        
        event_info = {
            "id": action.eventId,
            "eid": action.eventId,  # 前端使用 eid 字段
            "eventId": action.eventId,  # 兼容性字段
            "name": get_action_name(action),
            "type": event_type,
            "flags": flags,
            "depth": depth,
            "numIndices": action.numIndices,
            "numInstances": action.numInstances,
            "parent": action.parent.eventId if action.parent else None,
            "parentEid": action.parent.eventId if action.parent else None,  # 兼容性字段
            "duration": 0,  # GPU timing 需要额外提取
            "hasChildren": has_children,
            "childCount": child_count,
            "shaders": [],
            "textures": [],
            "renderTargets": [],
        }
        events_data.append(event_info)
        
        if (i + 1) % 200 == 0:
            print(f"    Processed {i + 1}/{min(len(all_actions), args.max_events)} events...")
    
    print(f"  Extracted {len(events_data)} events")
    
    # ------------------------------------------------------------------------
    # 导出 RT 快照（可选）
    # ------------------------------------------------------------------------
    
    rt_snapshots_dir = output_dir / "rt_snapshots"
    rt_map = {}  # eid -> rt_filename
    
    if args.export_rt:
        print("[5.5/6] Exporting RT snapshots for draw events...")
        rt_snapshots_dir.mkdir(exist_ok=True)
        
        # 筛选需要导出的 Draw/Dispatch 事件
        draw_events = [(action, depth) for action, depth in all_actions[:args.max_events]
                       if action.flags & (rd.ActionFlags.Drawcall | rd.ActionFlags.Dispatch)]
        
        total_draws = len(draw_events)
        exported_count = 0
        failed_count = 0
        
        print(f"  Found {total_draws} draw/dispatch events")
        
        for i, (action, depth) in enumerate(draw_events):
            # 跳过间隔
            if args.rt_skip_interval > 1 and i % args.rt_skip_interval != 0:
                continue
            
            eid = action.eventId
            rt_path = rt_snapshots_dir / f"rt_{eid}.png"
            
            try:
                # 跳转到该事件
                controller.SetFrameEvent(eid, True)
                
                # 获取 Pipeline State
                state = controller.GetPipelineState()
                
                # 获取绑定的 RT（使用通用 API，适用于所有图形 API）
                rt_resource_id = None
                try:
                    # 优先获取 Color Output Targets
                    output_targets = state.GetOutputTargets()
                    for ot in output_targets:
                        res_id = ot.resource if hasattr(ot, 'resource') else None
                        # ResourceId 转字符串检查是否为空
                        if res_id and str(res_id) != 'ResourceId::0':
                            rt_resource_id = res_id
                            break
                    
                    # 如果没有 Color Target，尝试 Depth Target（用于 depth-only pass）
                    if not rt_resource_id:
                        depth_target = state.GetDepthTarget()
                        if depth_target:
                            res_id = depth_target.resource if hasattr(depth_target, 'resource') else None
                            if res_id and str(res_id) != 'ResourceId::0':
                                rt_resource_id = res_id
                except Exception as e:
                    pass
                
                if not rt_resource_id:
                    failed_count += 1
                    continue
                
                # 导出纹理
                save = rd.TextureSave()
                save.resourceId = rt_resource_id
                save.destType = rd.FileType.PNG
                save.mip = 0
                save.slice.sliceIndex = 0
                
                result = controller.SaveTexture(save, str(rt_path))
                
                if result == rd.ResultCode.Succeeded and rt_path.exists():
                    # 如果需要缩小尺寸
                    try:
                        from PIL import Image
                        img = Image.open(str(rt_path))
                        if img.width > args.rt_max_size or img.height > args.rt_max_size:
                            img.thumbnail((args.rt_max_size, args.rt_max_size), Image.LANCZOS)
                            img.save(str(rt_path), 'PNG')
                    except ImportError:
                        pass  # PIL 不可用则保持原图
                    
                    rt_map[eid] = f"rt_snapshots/rt_{eid}.png"
                    exported_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
            
            # 进度报告
            if (i + 1) % 50 == 0:
                print(f"    Processed {i + 1}/{total_draws} draws, exported {exported_count}...")
        
        print(f"  Exported {exported_count} RT snapshots, {failed_count} failed/skipped")
        
        # 更新事件数据，添加 RT 路径
        for event in events_data:
            eid = event.get('eid')
            if eid in rt_map:
                event['rtSnapshot'] = rt_map[eid]
    
    # ------------------------------------------------------------------------
    # 生成报告
    # ------------------------------------------------------------------------
    
    print("[6/6] Generating HTML report bundle...")
    
    try:
        from report_bundle_generator import ReportBundleGenerator
        
        generator = ReportBundleGenerator(str(output_dir), rdc_path.stem)
        
        # 设置纹理数据
        generator.set_textures(textures_data)
        
        # 设置事件数据
        generator.set_events(events_data)
        
        # 设置 Shader 数据（暂时为空，后续可扩展）
        generator.set_shaders([])
        
        # 直接更新 stats（ReportBundleGenerator 内部会自动计算部分统计）
        generator.stats["draw_calls"] = sum(1 for a, _ in all_actions if a.flags & rd.ActionFlags.Drawcall)
        generator.stats["dispatch_calls"] = sum(1 for a, _ in all_actions if a.flags & rd.ActionFlags.Dispatch)
        
        # 生成报告
        files = generator.generate_all()
        
        print()
        print("=" * 70)
        print("Report generated successfully!")
        print("=" * 70)
        print(f"Output directory: {output_dir}")
        print("Files:")
        for name in sorted(files.keys()):
            print(f"  - {name}")
        
    except ImportError as e:
        print(f"[WARNING] Could not import report_bundle_generator: {e}")
        print("  Falling back to JSON output only...")
        
        # 降级：只输出 JSON 数据
        json_data = {
            "overview": {
                "captureFile": str(rdc_path),
                "api": api_name,
                "totalEvents": len(all_actions),
                "totalTextures": len(textures_desc),
            },
            "textures": textures_data,
            "events": events_data,
        }
        
        json_path = output_dir / "report_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {json_path}")
    
    # ========================================================================
    # 清理
    # ========================================================================
    
    controller.Shutdown()
    cap.Shutdown()
    rd.ShutdownReplay()
    
    # 清理临时目录
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    print()
    print("Done!")


if __name__ == '__main__':
    main()
