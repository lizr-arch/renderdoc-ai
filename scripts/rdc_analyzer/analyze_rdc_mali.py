#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立 Mali Shader 分析脚本
========================

通过 renderdoccmd 执行，分析 RDC 文件中的 Shader。

使用方法:
    renderdoccmd --python analyze_rdc_mali.py -- <rdc_file>
"""

import sys
import os
import json
import subprocess
import tempfile
import re
from pathlib import Path

# RDC 文件路径
RDC_PATH = r"d:\Downloads\Game_x64h_2026.01.07_05.35.50_frame3996.rdc"
MALIOC_PATH = r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe"
OUTPUT_DIR = r"d:\Code\git\renderdoc\scripts\rdc_analyzer\output"
TARGET_GPU = "Mali-G78"

def detect_shader_format(source):
    """检测 Shader 格式"""
    source = source.strip()
    
    # GLSL 特征
    if re.search(r'#version\s+\d+', source) or re.search(r'\bgl_Position\b', source):
        return 'GLSL'
    
    # HLSL 特征
    if re.search(r'\bcbuffer\b', source) or re.search(r':\s*SV_\w+', source):
        return 'HLSL'
    
    # DXBC 特征
    if re.search(r'^(vs|ps|cs)_\d+_\d+', source, re.MULTILINE):
        return 'DXBC'
    
    return 'UNKNOWN'

def convert_hlsl_to_glsl(source, stage):
    """简单的 HLSL -> GLSL 转换"""
    glsl = source
    
    # 添加版本声明
    if not glsl.strip().startswith('#version'):
        glsl = "#version 300 es\nprecision highp float;\n\n" + glsl
    
    # 类型替换
    replacements = [
        (r'\bfloat2\b', 'vec2'), (r'\bfloat3\b', 'vec3'), (r'\bfloat4\b', 'vec4'),
        (r'\bfloat4x4\b', 'mat4'), (r'\bfloat3x3\b', 'mat3'),
        (r'\bhalf\b', 'float'), (r'\bhalf4\b', 'vec4'),
        (r'\blerp\s*\(', 'mix('), (r'\bfrac\s*\(', 'fract('),
        (r'\bsaturate\s*\(', 'clamp('), (r'\brsqrt\s*\(', 'inversesqrt('),
    ]
    for pattern, repl in replacements:
        glsl = re.sub(pattern, repl, glsl)
    
    # 移除语义
    glsl = re.sub(r'\s*:\s*SV_\w+', '', glsl)
    glsl = re.sub(r'\s*:\s*POSITION\d*', '', glsl)
    glsl = re.sub(r'\s*:\s*TEXCOORD\d*', '', glsl)
    glsl = re.sub(r'\s*:\s*register\s*\([^)]+\)', '', glsl)
    
    # cbuffer -> uniform
    glsl = re.sub(r'\bcbuffer\s+(\w+)', r'uniform \1', glsl)
    
    # Texture2D -> sampler2D
    glsl = re.sub(r'\bTexture2D\b', 'sampler2D', glsl)
    
    return glsl

def generate_dxbc_stub(source, stage):
    """从 DXBC 生成 GLSL stub"""
    # 分析 DXBC
    temp_regs = 4
    tex_count = 0
    cb_count = 1
    inst_count = 0
    shader_model = "unknown"
    
    for line in source.split('\n'):
        line = line.strip()
        if re.match(r'(vs|ps|cs)_\d+_\d+', line):
            shader_model = line
        if line.startswith('dcl_temps'):
            m = re.search(r'(\d+)', line)
            if m: temp_regs = int(m.group(1))
        if 'dcl_resource' in line or 'dcl_sampler' in line:
            tex_count += 1
        if line.startswith('dcl_constantbuffer'):
            cb_count += 1
        if not line.startswith('dcl_') and not line.startswith(';'):
            if any(line.startswith(op) for op in ['mov', 'add', 'mul', 'mad', 'sample', 'ret']):
                inst_count += 1
    
    # 生成 GLSL
    lines = [
        "#version 300 es",
        "precision highp float;",
        f"// Generated from {shader_model}, {inst_count} instructions",
        ""
    ]
    
    if stage == 'vertex':
        lines.extend(["in vec4 a_position;", "out vec4 v_color;", ""])
    else:
        lines.extend(["in vec4 v_color;", "out vec4 fragColor;", ""])
    
    for i in range(min(cb_count, 2)):
        lines.append(f"uniform vec4 u_data{i}[16];")
    for i in range(min(tex_count, 4)):
        lines.append(f"uniform sampler2D u_tex{i};")
    
    lines.extend(["", "void main() {"])
    
    for i in range(min(temp_regs, 8)):
        lines.append(f"    vec4 r{i} = vec4(0.0);")
    
    lines.extend([
        "",
        "    r0 = u_data0[0];",
        "    r1 = r0 * u_data0[1];",
        "    r0 = r0 + r1;",
        ""
    ])
    
    if stage == 'vertex':
        lines.extend(["    gl_Position = r0;", "    v_color = r0;"])
    else:
        if tex_count > 0:
            lines.append("    r0 = r0 * texture(u_tex0, v_color.xy);")
        lines.append("    fragColor = r0;")
    
    lines.append("}")
    return "\n".join(lines)

def run_malioc(glsl_source, shader_type, shader_name):
    """运行 malioc 分析"""
    if not os.path.exists(MALIOC_PATH):
        return {'error': f'malioc not found: {MALIOC_PATH}'}
    
    # 写入临时文件
    suffix = '.vert' if shader_type == 'vertex' else '.frag'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(glsl_source)
        glsl_path = f.name
    
    try:
        # 运行 malioc
        stage_flag = '--vertex' if shader_type == 'vertex' else '--fragment'
        cmd = [MALIOC_PATH, '--format', 'json', '--core', TARGET_GPU, stage_flag, glsl_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return parse_malioc_output(data, shader_name, shader_type)
            except json.JSONDecodeError:
                return {'error': 'Failed to parse malioc JSON output', 'raw': result.stdout[:500]}
        else:
            return {'error': result.stderr[:500] if result.stderr else 'Unknown error'}
    except Exception as e:
        return {'error': str(e)}
    finally:
        if os.path.exists(glsl_path):
            os.unlink(glsl_path)

def parse_malioc_output(data, shader_name, shader_type):
    """解析 malioc JSON 输出"""
    result = {
        'name': shader_name,
        'type': shader_type,
        'success': True,
        'cycles': {},
        'registers': {},
        'bound': 'Unknown'
    }
    
    try:
        shaders = data.get('shaders', [])
        if not shaders:
            return {'error': 'No shader data in output'}
        
        shader = shaders[0]
        variants = shader.get('variants', [])
        if not variants:
            return {'error': 'No variants in shader data'}
        
        variant = variants[0]
        props = variant.get('properties', [])
        perf = variant.get('performance', {})
        
        # 解析属性
        for prop in props:
            name = prop.get('name', '')
            value = prop.get('value', 0)
            if 'work_registers' in name.lower():
                result['registers']['work'] = value
            elif 'uniform_registers' in name.lower():
                result['registers']['uniform'] = value
            elif 'stack_spill' in name.lower():
                result['registers']['stack_spilling'] = value
        
        # 解析周期
        pipelines = perf.get('pipelines', [])
        cycles = perf.get('shortest_path_cycles', {}).get('cycle_count', [])
        bound_idx = perf.get('shortest_path_cycles', {}).get('bound_pipelines', [0])[0] if perf.get('shortest_path_cycles', {}).get('bound_pipelines') else 0
        
        cycle_map = {'A': 0, 'LS': 0, 'T': 0, 'V': 0}
        for i, name in enumerate(pipelines):
            if i < len(cycles):
                n = name.lower()
                if 'arith' in n or n == 'a':
                    cycle_map['A'] = cycles[i]
                elif 'load' in n or 'store' in n or n == 'ls':
                    cycle_map['LS'] = cycles[i]
                elif 'tex' in n or n == 't':
                    cycle_map['T'] = cycles[i]
                elif 'vary' in n or n == 'v':
                    cycle_map['V'] = cycles[i]
        
        result['cycles'] = {
            'arithmetic': cycle_map['A'],
            'load_store': cycle_map['LS'],
            'texture': cycle_map['T'],
            'varying': cycle_map['V'],
            'total': max(cycle_map.values()) if cycle_map.values() else 0
        }
        
        # 确定瓶颈
        max_cycle = max(cycle_map.values()) if cycle_map.values() else 0
        for unit, val in cycle_map.items():
            if val == max_cycle and val > 0:
                bound_names = {'A': 'Arithmetic', 'LS': 'Load/Store', 'T': 'Texture', 'V': 'Varying'}
                result['bound'] = bound_names.get(unit, unit)
                break
        
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
    
    return result

def generate_html_report(results, output_path):
    """生成 HTML 报告"""
    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mali Shader Analysis Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; margin: 0; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
        h2 { color: #ff6b6b; margin-top: 30px; }
        .shader-card { background: #16213e; border-radius: 8px; padding: 20px; margin: 15px 0; border-left: 4px solid #00d4ff; }
        .shader-card.error { border-left-color: #ff6b6b; }
        .shader-name { font-size: 1.2em; font-weight: bold; color: #00d4ff; }
        .shader-type { color: #888; font-size: 0.9em; margin-left: 10px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }
        .metric { background: #0f3460; padding: 15px; border-radius: 6px; }
        .metric-label { color: #888; font-size: 0.85em; }
        .metric-value { font-size: 1.5em; font-weight: bold; color: #4ecca3; margin-top: 5px; }
        .cycle-bar { height: 20px; background: #0f3460; border-radius: 4px; margin: 5px 0; overflow: hidden; }
        .cycle-fill { height: 100%; border-radius: 4px; }
        .cycle-fill.arith { background: linear-gradient(90deg, #ff6b6b, #ee5a24); }
        .cycle-fill.ls { background: linear-gradient(90deg, #4ecca3, #38ada9); }
        .cycle-fill.tex { background: linear-gradient(90deg, #00d4ff, #0097e6); }
        .cycle-fill.vary { background: linear-gradient(90deg, #9b59b6, #8e44ad); }
        .bound-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; margin-left: 10px; }
        .bound-badge.arithmetic { background: #ff6b6b; color: #fff; }
        .bound-badge.texture { background: #00d4ff; color: #000; }
        .bound-badge.load-store { background: #4ecca3; color: #000; }
        .summary { background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; }
        .summary-item { }
        .summary-value { font-size: 2em; font-weight: bold; color: #00d4ff; }
        .summary-label { color: #888; margin-top: 5px; }
        .error-msg { color: #ff6b6b; font-style: italic; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #0f3460; color: #00d4ff; }
    </style>
</head>
<body>
<div class="container">
    <h1>Mali Shader Analysis Report</h1>
    <p>Target GPU: <strong>''' + TARGET_GPU + '''</strong> | RDC: <strong>''' + os.path.basename(RDC_PATH) + '''</strong></p>
'''
    
    # Summary
    success_count = sum(1 for r in results if r.get('success'))
    total_arith = sum(r.get('cycles', {}).get('arithmetic', 0) for r in results if r.get('success'))
    total_tex = sum(r.get('cycles', {}).get('texture', 0) for r in results if r.get('success'))
    
    html += f'''
    <div class="summary">
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-value">{len(results)}</div>
                <div class="summary-label">Total Shaders</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{success_count}</div>
                <div class="summary-label">Analyzed</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{total_arith:.1f}</div>
                <div class="summary-label">Total Arith Cycles</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{total_tex:.1f}</div>
                <div class="summary-label">Total Tex Cycles</div>
            </div>
        </div>
    </div>
'''
    
    # Shader details
    html += '<h2>Shader Details</h2>'
    
    for r in results:
        card_class = 'shader-card' if r.get('success') else 'shader-card error'
        html += f'<div class="{card_class}">'
        html += f'<span class="shader-name">{r.get("name", "Unknown")}</span>'
        html += f'<span class="shader-type">({r.get("type", "unknown")})</span>'
        
        if r.get('success'):
            bound = r.get('bound', 'Unknown').lower().replace('/', '-')
            html += f'<span class="bound-badge {bound}">Bound: {r.get("bound", "?")}</span>'
            
            cycles = r.get('cycles', {})
            max_cycle = max(cycles.get('arithmetic', 1), cycles.get('texture', 1), cycles.get('load_store', 1), cycles.get('varying', 1), 1)
            
            html += '<div class="metrics">'
            for unit, key, cls in [('Arithmetic', 'arithmetic', 'arith'), ('Load/Store', 'load_store', 'ls'), ('Texture', 'texture', 'tex'), ('Varying', 'varying', 'vary')]:
                val = cycles.get(key, 0)
                pct = (val / max_cycle * 100) if max_cycle > 0 else 0
                html += f'''
                <div class="metric">
                    <div class="metric-label">{unit}</div>
                    <div class="metric-value">{val:.1f}</div>
                    <div class="cycle-bar"><div class="cycle-fill {cls}" style="width: {pct}%"></div></div>
                </div>'''
            html += '</div>'
            
            regs = r.get('registers', {})
            if regs:
                html += f'<p style="margin-top:15px;color:#888;">Registers: Work={regs.get("work", "?")} | Uniform={regs.get("uniform", "?")}</p>'
        else:
            html += f'<p class="error-msg">Error: {r.get("error", "Unknown error")}</p>'
        
        html += '</div>'
    
    html += '''
</div>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path

def main():
    import renderdoc as rd
    
    print(f"Opening RDC: {RDC_PATH}")
    
    # 打开捕获文件
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(RDC_PATH, '', None)
    
    if result != rd.ResultCode.Succeeded:
        print(f"Failed to open RDC: {result}")
        return
    
    print(f"API: {cap.DriverName()}")
    
    # 创建回放控制器
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        print(f"Failed to create replay controller: {status}")
        cap.Shutdown()
        return
    
    # 获取反汇编目标
    disasm_targets = controller.GetDisassemblyTargets(True)
    print(f"Available disasm targets: {list(disasm_targets)}")
    
    # 选择目标
    target = None
    for t in disasm_targets:
        target = t
        break
    
    if not target:
        print("No disassembly target available")
        controller.Shutdown()
        cap.Shutdown()
        return
    
    print(f"Using target: {target}")
    
    # 获取 Draw Calls
    actions = controller.GetRootActions()
    
    def find_draw_calls(action_list, depth=0):
        result = []
        for action in action_list:
            if action.flags & rd.ActionFlags.Drawcall:
                result.append(action)
            if len(action.children) > 0:
                result.extend(find_draw_calls(action.children, depth + 1))
        return result
    
    draw_calls = find_draw_calls(actions)
    print(f"Found {len(draw_calls)} draw calls")
    
    # 分析前几个唯一 Shader
    results = []
    analyzed_shaders = set()
    max_shaders = 10  # 分析最多10个
    
    for dc in draw_calls:
        if len(analyzed_shaders) >= max_shaders * 2:  # VS + PS
            break
        
        event_id = dc.eventId
        controller.SetFrameEvent(event_id, True)
        state = controller.GetPipelineState()
        pipe = state.GetGraphicsPipelineObject()
        
        # Vertex Shader
        try:
            vs_refl = state.GetShaderReflection(rd.ShaderStage.Vertex)
            if vs_refl and vs_refl.resourceId not in analyzed_shaders:
                vs_source = controller.DisassembleShader(pipe, vs_refl, target)
                if vs_source and len(vs_source) > 50:
                    shader_name = f"VS_EID{event_id}"
                    fmt = detect_shader_format(vs_source)
                    print(f"  {shader_name}: format={fmt}, len={len(vs_source)}")
                    
                    # 转换
                    if fmt == 'GLSL':
                        glsl = vs_source
                    elif fmt == 'HLSL':
                        glsl = convert_hlsl_to_glsl(vs_source, 'vertex')
                    else:
                        glsl = generate_dxbc_stub(vs_source, 'vertex')
                    
                    # 分析
                    result = run_malioc(glsl, 'vertex', shader_name)
                    results.append(result)
                    analyzed_shaders.add(vs_refl.resourceId)
        except Exception as e:
            print(f"  VS error: {e}")
        
        # Pixel Shader
        try:
            ps_refl = state.GetShaderReflection(rd.ShaderStage.Pixel)
            if ps_refl and ps_refl.resourceId not in analyzed_shaders:
                ps_source = controller.DisassembleShader(pipe, ps_refl, target)
                if ps_source and len(ps_source) > 50:
                    shader_name = f"PS_EID{event_id}"
                    fmt = detect_shader_format(ps_source)
                    print(f"  {shader_name}: format={fmt}, len={len(ps_source)}")
                    
                    # 转换
                    if fmt == 'GLSL':
                        glsl = ps_source
                    elif fmt == 'HLSL':
                        glsl = convert_hlsl_to_glsl(ps_source, 'fragment')
                    else:
                        glsl = generate_dxbc_stub(ps_source, 'fragment')
                    
                    # 分析
                    result = run_malioc(glsl, 'fragment', shader_name)
                    results.append(result)
                    analyzed_shaders.add(ps_refl.resourceId)
        except Exception as e:
            print(f"  PS error: {e}")
    
    # 生成报告
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "mali_shader_report.html")
    generate_html_report(results, report_path)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Analyzed {len(results)} shaders")
    print(f"Report: {report_path}")
    
    # 打印摘要
    for r in results:
        if r.get('success'):
            cycles = r.get('cycles', {})
            print(f"  {r['name']}: A={cycles.get('arithmetic', 0):.1f} T={cycles.get('texture', 0):.1f} Bound={r.get('bound', '?')}")
        else:
            print(f"  {r['name']}: ERROR - {r.get('error', '?')[:50]}")
    
    controller.Shutdown()
    cap.Shutdown()

if __name__ == "__main__":
    main()
