#!/usr/bin/env python3
"""
RDC → 4 页面分析报告 一键生成器

在 RenderDoc Python Shell 中运行此脚本，自动生成包含以下内容的完整报告：
1. 概览页 (overview.html) - 统计数据和分析摘要
2. 纹理页 (textures.html) - 纹理列表和**真实缩略图**
3. Shader 页 (shaders.html) - Shader 列表和**真实 HLSL 源码**
4. 事件页 (events.html) - Draw Call 事件列表

用法（在 RenderDoc Python Shell 中）:
    exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\rdc_to_bundle_report.py').read())

或者指定输出目录:
    OUTPUT_DIR = r'd:\\path\\to\\output'
    exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\rdc_to_bundle_report.py').read())

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import os
import sys
import json
import base64
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# ============================================================================
# 配置
# ============================================================================

SCRIPT_DIR = Path(r'd:\Code\git\renderdoc\scripts\rdc_analyzer')
THUMBNAIL_MAX_SIZE = 128  # 缩略图最大尺寸
MAX_SHADERS = 100  # 最大提取 Shader 数量
MAX_EVENTS = 500  # 最大提取事件数量

# RT 快照配置
EXTRACT_RT_SNAPSHOTS = True  # 是否提取 Render Target 快照
RT_SNAPSHOT_MAX_SIZE = 256   # RT 快照最大尺寸（像素）
RT_SNAPSHOT_INTERVAL = 1     # 每隔 N 个 Draw Call 提取一次（1=全部）

# 添加脚本目录到 Python 路径
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

print("=" * 70)
print("RDC → 4 Page Report Generator")
print("=" * 70)

# ============================================================================
# 检查 RenderDoc 环境
# ============================================================================

try:
    ctx = pyrenderdoc.GetCaptureContext()
    rd = renderdoc
    
    if ctx is None or not ctx.IsCaptureLoaded():
        print("[ERROR] No capture loaded. Please open an RDC file first!")
        raise SystemExit
    
    cap_file = ctx.GetCaptureFilename()
    if not cap_file:
        print("[ERROR] Cannot get capture filename.")
        raise SystemExit
    
    cap_path = Path(cap_file)
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

# 输出目录配置
if 'OUTPUT_DIR' not in dir():
    OUTPUT_DIR = cap_path.parent / f"{cap_path.stem}_report"
else:
    OUTPUT_DIR = Path(OUTPUT_DIR)

OUTPUT_DIR = Path(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[INFO] Output: {OUTPUT_DIR}")

# ============================================================================
# 获取回放控制器
# ============================================================================

replay = ctx.Replay()
if replay is None:
    print("[ERROR] No replay available")
    raise SystemExit

controller = replay.GetController()
if controller is None:
    print("[ERROR] No replay controller available")
    raise SystemExit

# ============================================================================
# Step 0.5: 检测 ZIP+XML 导出文件（用于 Vulkan 内存别名场景的正确缩略图提取）
# ============================================================================

thumb_gen = None
thumb_gen_extractable = {}  # {resource_id: (ImageInfo, MemoryBinding, InitialContents)}

# 检测同目录下是否有 ZIP 文件
potential_zips = [
    cap_path.with_suffix('.zip'),  # same_name.zip
    cap_path.parent / 'frame.zip',  # frame.zip (常见导出名)
    cap_path.parent / f'{cap_path.stem}.zip',  # capture_name.zip
]

zip_path = None
xml_path = None

for zp in potential_zips:
    if zp.exists():
        # 检查对应的 XML 文件
        xp = zp.with_suffix('.zip.xml')
        if not xp.exists():
            xp = zp.with_suffix('.xml')
        if xp.exists():
            zip_path = zp
            xml_path = xp
            break

if zip_path and xml_path:
    print(f"[INFO] Found ZIP export: {zip_path.name}")
    print(f"[INFO] Found XML export: {xml_path.name}")
    
    try:
        from thumbnail_generator import ThumbnailGenerator
        
        thumb_gen = ThumbnailGenerator(str(xml_path), str(zip_path))
        thumb_gen.parse()
        
        # 构建可提取纹理的映射
        extractable = thumb_gen.get_extractable_textures()
        for img, binding, ic in extractable:
            thumb_gen_extractable[img.resource_id] = (img, binding, ic)
        
        print(f"[INFO] ThumbnailGenerator ready: {len(thumb_gen_extractable)} extractable textures")
        print(f"[INFO] Will use offset-aware extraction for Vulkan memory aliasing")
    except ImportError:
        print("[WARN] ThumbnailGenerator module not available, using SaveTexture fallback")
        thumb_gen = None
    except Exception as e:
        print(f"[WARN] ThumbnailGenerator init failed: {e}, using SaveTexture fallback")
        thumb_gen = None
else:
    print("[INFO] No ZIP+XML export found, using standard SaveTexture API")
    print("[INFO] To enable offset-aware extraction, export capture as ZIP+XML first")

# ============================================================================
# Step 1: 提取纹理信息和缩略图
# ============================================================================

print()
print("[1/4] Extracting textures and thumbnails...")

textures_desc = controller.GetTextures()
print(f"  Found {len(textures_desc)} textures")

temp_dir = Path(tempfile.mkdtemp(prefix="rdoc_bundle_"))
textures_data = []
total_vram = 0
thumb_from_gen = 0  # 从 ThumbnailGenerator 提取的缩略图数
thumb_from_api = 0  # 从 SaveTexture API 提取的缩略图数

for i, tex in enumerate(textures_desc):
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
    
    # 简化纹理名称: #tex_{id} ({width}x{height})
    display_name = f"#tex_{res_id} ({width}×{height})"
    
    # 简化格式名称
    simple_format = fmt_name
    for prefix in ['VK_FORMAT_', 'DXGI_FORMAT_', 'GL_']:
        if simple_format.startswith(prefix):
            simple_format = simple_format[len(prefix):]
    
    tex_info = {
        "id": res_id,
        "name": display_name,
        "raw_name": f"Texture_{res_id}_{width}x{height}_{fmt_name}",
        "width": width,
        "height": height,
        "depth": depth,
        "format": simple_format,
        "format_full": fmt_name,
        "mips": tex.mips,
        "arrayLayers": tex.arraysize,
        "estimated_size": estimated_size,
        "type": str(tex.type).replace("TextureType.", ""),
        "thumbnail": None,  # 待填充
    }
    
    # 提取缩略图 - 优先使用 ThumbnailGenerator（解决 Vulkan 内存别名问题）
    thumb_extracted = False
    
    # 方法1: ThumbnailGenerator（offset-aware，适用于 Vulkan 内存别名）
    if thumb_gen and res_id in thumb_gen_extractable:
        try:
            img_info, binding, ic = thumb_gen_extractable[res_id]
            result = thumb_gen.generate_thumbnail(img_info, binding, ic, max_size=THUMBNAIL_MAX_SIZE)
            if result.success and result.base64_data:
                tex_info["thumbnail"] = result.base64_data
                thumb_extracted = True
                thumb_from_gen += 1
        except Exception as e:
            pass  # 回退到 SaveTexture
    
    # 方法2: RenderDoc SaveTexture API（回退方案）
    if not thumb_extracted:
        temp_file = temp_dir / f"thumb_{res_id}.png"
        
        try:
            save_data = rd.TextureSave()
            save_data.resourceId = tex.resourceId
            save_data.destType = rd.FileType.PNG
            save_data.alpha = rd.AlphaMapping.Preserve
            
            # 选择合适的 mip level
            mip_to_use = 0
            w, h = width, height
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
                thumb_extracted = True
                thumb_from_api += 1
        except Exception as e:
            pass  # 缩略图提取失败，保持 None
    
    textures_data.append(tex_info)
    
    if (i + 1) % 50 == 0:
        print(f"  Progress: {i + 1}/{len(textures_desc)}")

print(f"  [OK] Extracted {len(textures_data)} textures")
print(f"  [OK] Total VRAM: {total_vram / (1024*1024):.2f} MB")

# 统计有缩略图的纹理
thumb_count = sum(1 for t in textures_data if t.get('thumbnail'))
print(f"  [OK] Thumbnails: {thumb_count}/{len(textures_data)}")
if thumb_from_gen > 0 or thumb_from_api > 0:
    print(f"       - ThumbnailGenerator (offset-aware): {thumb_from_gen}")
    print(f"       - SaveTexture API (fallback): {thumb_from_api}")

# ============================================================================
# Step 2: 提取 Shader 信息和源码
# ============================================================================

print()
print("[2/4] Extracting shaders and HLSL source...")

# 获取所有 Draw Call
actions = controller.GetRootActions()

def flatten_actions(action_list):
    result = []
    for action in action_list:
        result.append(action)
        if len(action.children) > 0:
            result.extend(flatten_actions(action.children))
    return result

all_actions = flatten_actions(actions)
draw_actions = [a for a in all_actions if a.flags & rd.ActionFlags.Drawcall]

print(f"  Found {len(draw_actions)} draw calls")

# 获取反汇编目标格式
targets = controller.GetDisassemblyTargets(True)
preferred_targets = ['GLSL', 'HLSL', 'SPIR-V']
target = None

for pref in preferred_targets:
    for t in targets:
        if pref.lower() in str(t).lower():
            target = t
            break
    if target:
        break

if not target and targets:
    target = targets[0]

print(f"  Disassembly target: {target if target else 'None'}")

shaders_data = []
seen_shaders = {}  # shader_id -> shader_info

for i, action in enumerate(draw_actions[:MAX_SHADERS]):
    try:
        controller.SetFrameEvent(action.eventId, True)
        state = controller.GetPipelineState()
        pipeline = state.GetGraphicsPipelineObject()
        
        # Vertex Shader
        vs_refl = state.GetShaderReflection(rd.ShaderStage.Vertex)
        if vs_refl:
            vs_id = str(state.GetShader(rd.ShaderStage.Vertex))
            if vs_id not in seen_shaders:
                shader_info = {
                    "id": f"vs_{action.eventId}",
                    "name": f"VS @ Event {action.eventId}",
                    "type": "Vertex",
                    "stage": "Vertex",
                    "entry_point": vs_refl.entryPoint if hasattr(vs_refl, 'entryPoint') else "main",
                    "source": "",
                    "event_id": action.eventId,
                }
                
                if target:
                    try:
                        source = controller.DisassembleShader(pipeline, vs_refl, target)
                        if source:
                            shader_info["source"] = source
                            shader_info["format"] = str(target)
                    except:
                        pass
                
                seen_shaders[vs_id] = shader_info
                shaders_data.append(shader_info)
        
        # Fragment/Pixel Shader
        ps_refl = state.GetShaderReflection(rd.ShaderStage.Fragment)
        if ps_refl:
            ps_id = str(state.GetShader(rd.ShaderStage.Fragment))
            if ps_id not in seen_shaders:
                shader_info = {
                    "id": f"ps_{action.eventId}",
                    "name": f"PS @ Event {action.eventId}",
                    "type": "Fragment",
                    "stage": "Fragment",
                    "entry_point": ps_refl.entryPoint if hasattr(ps_refl, 'entryPoint') else "main",
                    "source": "",
                    "event_id": action.eventId,
                }
                
                if target:
                    try:
                        source = controller.DisassembleShader(pipeline, ps_refl, target)
                        if source:
                            shader_info["source"] = source
                            shader_info["format"] = str(target)
                    except:
                        pass
                
                seen_shaders[ps_id] = shader_info
                shaders_data.append(shader_info)
                
    except Exception as e:
        continue
    
    if (i + 1) % 20 == 0:
        print(f"  Progress: {i + 1}/{min(len(draw_actions), MAX_SHADERS)}")

print(f"  [OK] Extracted {len(shaders_data)} unique shaders")

# 统计有源码的 shader
source_count = sum(1 for s in shaders_data if s.get('source'))
print(f"  [OK] With source: {source_count}/{len(shaders_data)}")

# ============================================================================
# Step 3: 提取事件信息
# ============================================================================

print()
print("[3/4] Extracting event information...")

events_data = []

for i, action in enumerate(all_actions[:MAX_EVENTS]):
    event_info = {
        "id": action.eventId,
        "name": action.customName if action.customName else f"Event_{action.eventId}",
        "flags": int(action.flags),
        "is_draw": bool(action.flags & rd.ActionFlags.Drawcall),
        "is_dispatch": bool(action.flags & rd.ActionFlags.Dispatch),
        "is_clear": bool(action.flags & rd.ActionFlags.Clear),
        "num_indices": action.numIndices if hasattr(action, 'numIndices') else 0,
        "num_instances": action.numInstances if hasattr(action, 'numInstances') else 1,
        "output": None,  # RT 快照占位符
    }
    events_data.append(event_info)

print(f"  [OK] Extracted {len(events_data)} events")

# ============================================================================
# Step 3.5: 提取 RT 快照（可选）
# ============================================================================

def get_bound_rt_ids(state):
    """从 Pipeline State 获取绑定的 RT Resource IDs"""
    rt_ids = []
    try:
        # 尝试获取 Output Merger / Render Pass 的 RT 绑定
        om = state.GetOutputMerger()
        if om:
            # D3D11/D3D12 风格
            if hasattr(om, 'renderTargets'):
                for rt in om.renderTargets:
                    if rt and hasattr(rt, 'resourceId') and int(rt.resourceId) != 0:
                        rt_ids.append(int(rt.resourceId))
            # Vulkan 风格
            elif hasattr(om, 'colorAttachments'):
                for att in om.colorAttachments:
                    if att and hasattr(att, 'imageView') and hasattr(att.imageView, 'resourceId'):
                        rt_ids.append(int(att.imageView.resourceId))
    except Exception as e:
        pass
    
    # 过滤无效 ID
    rt_ids = [rid for rid in rt_ids if rid > 0]
    return rt_ids[:4]  # 最多 4 个 RT

def export_texture_base64(resource_id: int, max_size: int) -> Optional[str]:
    """导出纹理为 Base64 PNG"""
    temp_file = temp_dir / f"rt_{resource_id}.png"
    
    try:
        save_data = rd.TextureSave()
        save_data.resourceId = rd.ResourceId.FromInt(resource_id)
        save_data.destType = rd.FileType.PNG
        save_data.alpha = rd.AlphaMapping.Preserve
        save_data.mip = 0
        
        # 设置缩放以限制大小
        tex_desc = controller.GetTexture(rd.ResourceId.FromInt(resource_id))
        if tex_desc:
            w, h = tex_desc.width, tex_desc.height
            if w > max_size or h > max_size:
                scale = max_size / max(w, h)
                save_data.scale = scale
        
        result = controller.SaveTexture(save_data, str(temp_file))
        
        if result == rd.ResultCode.Succeeded and temp_file.exists():
            with open(temp_file, 'rb') as f:
                img_data = f.read()
            temp_file.unlink()
            return f"data:image/png;base64,{base64.b64encode(img_data).decode('ascii')}"
    except Exception as e:
        pass
    
    return None

if EXTRACT_RT_SNAPSHOTS:
    print()
    print("[3.5/4] Extracting Render Target snapshots...")
    
    draw_count = 0
    rt_extracted = 0
    
    for event_info in events_data:
        if not event_info.get("is_draw"):
            continue
        
        draw_count += 1
        
        # 按间隔跳过
        if RT_SNAPSHOT_INTERVAL > 1 and draw_count % RT_SNAPSHOT_INTERVAL != 0:
            continue
        
        eid = event_info["id"]
        
        try:
            controller.SetFrameEvent(eid, True)
            state = controller.GetPipelineState()
            rt_ids = get_bound_rt_ids(state)
            
            if rt_ids:
                output = {}
                for slot, rt_id in enumerate(rt_ids):
                    img_base64 = export_texture_base64(rt_id, RT_SNAPSHOT_MAX_SIZE)
                    if img_base64:
                        output[f"color{slot}"] = img_base64
                
                if output:
                    event_info["output"] = output
                    rt_extracted += 1
                    
        except Exception as e:
            continue
        
        if draw_count % 50 == 0:
            print(f"  Progress: {draw_count} draws processed, {rt_extracted} RTs extracted")
    
    print(f"  [OK] Extracted RT snapshots for {rt_extracted} draw calls")

# ============================================================================
# Step 4: 生成 4 页面报告
# ============================================================================

print()
print("[4/4] Generating 4-page HTML report...")

# 准备报告数据
report_data = {
    "rdc_name": cap_path.name,
    "capture_time": datetime.now().isoformat(),
    
    # 纹理数据
    "textures": textures_data,
    "total_textures": len(textures_data),
    "total_vram": total_vram,
    
    # Shader 数据
    "shaders": shaders_data,
    "total_shaders": len(shaders_data),
    
    # 事件数据
    "events": events_data,
    "total_events": len(events_data),
    "total_draws": len(draw_actions),
    
    # API 信息
    "api": str(controller.GetAPIProperties().pipelineType) if hasattr(controller.GetAPIProperties(), 'pipelineType') else "Unknown",
}

# 导入报告生成器
try:
    from report_bundle_generator import ReportBundleGenerator
    
    # 创建生成器实例
    generator = ReportBundleGenerator(
        output_dir=str(OUTPUT_DIR),
        capture_name=cap_path.name,
    )
    
    # 构建资源使用索引（证据链数据基础）- 必须在 set_textures 之前
    texture_usage_map = {}
    shader_usage_map = {}
    try:
        from core.resource_usage_builder import ResourceUsageBuilder
        
        # 构造伪 ParsedData 对象
        class MockParsedData:
            def __init__(self, draws, textures, shaders):
                self.draws = draws
                self.dispatches = []
                self.textures = textures
                self.shaders = shaders
                self.render_passes = []
        
        parsed_data = MockParsedData(events_data, textures_data, shaders_data)
        builder = ResourceUsageBuilder()
        usage_index = builder.build(parsed_data)
        generator.set_resource_usage_index(usage_index)
        
        # 提取 texture_usage_map 和 shader_usage_map (转为 list of dict 格式)
        texture_usage_map = {
            k: [r.to_dict() for r in v]
            for k, v in usage_index.texture_usages.items()
        }
        shader_usage_map = {
            k: [r.to_dict() for r in v]
            for k, v in usage_index.shader_usages.items()
        }
        print(f"  [OK] Built resource usage index: {usage_index.get_statistics()}")
    except Exception as e:
        print(f"  [WARN] Failed to build resource usage index: {e}")
    
    # 设置纹理数据（传入 usage_map）
    generator.set_textures(textures_data, texture_usage_map)
    
    # 设置 Shader 数据（无 Mali 数据，传入 usage_map）
    generator.set_shaders(shaders_data, mali_data=None, usage_map=shader_usage_map)
    
    # 设置事件数据
    generator.set_events(events_data)
    
    # 注入统计数据
    generator.stats["total_textures"] = len(textures_data)
    generator.stats["total_shaders"] = len(shaders_data)
    generator.stats["total_events"] = len(events_data)
    generator.stats["draw_calls"] = len(draw_actions)
    generator.stats["vram_usage"] = total_vram
    
    # 生成报告
    output_files = generator.generate_all()
    
    print()
    print("=" * 70)
    print("[DONE] Report generation complete!")
    print()
    print(f"  Output Directory: {OUTPUT_DIR}")
    print()
    print("  Generated files:")
    for name, path in output_files.items():
        print(f"    - {name}: {Path(path).name}")
    print()
    print(f"  Open {OUTPUT_DIR / 'overview.html'} in browser to view.")
    print("=" * 70)
    
except ImportError as e:
    print(f"[ERROR] Cannot import report_bundle_generator: {e}")
    print()
    print("Falling back to JSON export...")
    
    # 回退到 JSON 导出
    json_path = OUTPUT_DIR / "report_data.json"
    
    # 移除 thumbnail 和 source 中的大数据
    export_data = {
        "capture": cap_path.name,
        "textures": [{k: v for k, v in t.items() if k != 'thumbnail' or v is None} 
                     for t in textures_data],
        "shaders": [{k: (v[:200] + '...' if k == 'source' and v and len(v) > 200 else v) 
                     for k, v in s.items()} 
                    for s in shaders_data],
        "events": events_data,
        "summary": {
            "textures": len(textures_data),
            "shaders": len(shaders_data),
            "events": len(events_data),
            "vram_mb": total_vram / (1024*1024),
        }
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"  [OK] JSON data saved to: {json_path}")

except Exception as e:
    print(f"[ERROR] Failed to generate report: {e}")
    import traceback
    traceback.print_exc()

# 清理临时目录
shutil.rmtree(temp_dir, ignore_errors=True)
