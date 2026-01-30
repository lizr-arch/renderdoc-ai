#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc Python Shell - Mali Shader 分析脚本 (v2.0)
====================================================

使用方法:
1. 在 RenderDoc 中打开 RDC 文件
2. 打开 Python Shell (Window -> Python Shell)
3. 复制粘贴此脚本内容到 Shell 中执行

新功能 (P3):
- GPU 模型选择 (支持 30+ 款 Mali GPU)
- JSON/CSV 导出
- 历史对比功能
- 增强的交互式报告

注意: 此脚本必须在 RenderDoc 的内置 Python Shell 中运行
"""

import subprocess
import tempfile
import json
import os
import re
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any

# ============== 配置 ==============
MALIOC_PATH = r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe"
OUTPUT_DIR = r"d:\Code\git\renderdoc\scripts\rdc_analyzer\output"
MAX_SHADERS = 100

# ============== 支持的 GPU 列表 ==============
SUPPORTED_GPUS = {
    # Arm 5th Gen
    "5th_gen": [
        "Immortalis-G925", "Immortalis-G720", 
        "Mali-G725", "Mali-G720", "Mali-G625", "Mali-G620"
    ],
    # Valhall
    "valhall": [
        "Immortalis-G715", "Mali-G715", "Mali-G710", "Mali-G615", "Mali-G610",
        "Mali-G510", "Mali-G310", "Mali-G78AE", "Mali-G78", "Mali-G77",
        "Mali-G68", "Mali-G57"
    ],
    # Bifrost
    "bifrost": [
        "Mali-G76", "Mali-G72", "Mali-G71", "Mali-G52", "Mali-G51", "Mali-G31"
    ],
    # Midgard
    "midgard": [
        "Mali-T880", "Mali-T860", "Mali-T830", "Mali-T820", "Mali-T760", "Mali-T720"
    ]
}

# 默认 GPU 和常用 GPU 快捷选项
DEFAULT_GPU = "Mali-G78"
POPULAR_GPUS = ["Mali-G78", "Mali-G77", "Mali-G710", "Mali-G57", "Mali-G76", "Immortalis-G720"]

# ============== 全局配置 ==============
class AnalyzerConfig:
    """分析器配置"""
    def __init__(self):
        self.target_gpu = DEFAULT_GPU
        self.max_shaders = MAX_SHADERS
        self.output_dir = OUTPUT_DIR
        self.save_json = True
        self.save_csv = True
        self.compare_history = True

CONFIG = AnalyzerConfig()

# ============== Shader 编码类型映射 ==============
ENCODING_NAMES = {
    0: 'Unknown', 1: 'DXBC', 2: 'DXIL', 3: 'GLSL', 4: 'SPIRV',
    5: 'SPIRVAsm', 6: 'HLSL', 7: 'OpenGLSPIRV', 8: 'OpenGLSPIRVAsm', 9: 'Slang',
}

def get_encoding_name(encoding):
    if hasattr(encoding, 'value'):
        return ENCODING_NAMES.get(encoding.value, str(encoding))
    if hasattr(encoding, '__int__'):
        return ENCODING_NAMES.get(int(encoding), str(encoding))
    return str(encoding)

# ============== Shader 格式检测与转换 ==============
def detect_format(source):
    if re.search(r'#version\s+\d+', source):
        return 'GLSL'
    if re.search(r'\bcbuffer\b', source) or re.search(r':\s*SV_\w+', source):
        return 'HLSL'
    if re.search(r'^(vs|ps|cs)_\d+_\d+', source, re.MULTILINE):
        return 'DXBC'
    return 'UNKNOWN'

def hlsl_to_glsl(source, stage):
    glsl = source
    if not glsl.strip().startswith('#version'):
        glsl = "#version 300 es\nprecision highp float;\n\n" + glsl
    
    repls = [
        (r'\bfloat2\b', 'vec2'), (r'\bfloat3\b', 'vec3'), (r'\bfloat4\b', 'vec4'),
        (r'\bfloat4x4\b', 'mat4'), (r'\bfloat3x3\b', 'mat3'),
        (r'\bhalf\b', 'float'), (r'\bhalf4\b', 'vec4'),
        (r'\blerp\s*\(', 'mix('), (r'\bfrac\s*\(', 'fract('),
    ]
    for p, r in repls:
        glsl = re.sub(p, r, glsl)
    
    glsl = re.sub(r'\s*:\s*SV_\w+', '', glsl)
    glsl = re.sub(r'\s*:\s*POSITION\d*', '', glsl)
    glsl = re.sub(r'\s*:\s*TEXCOORD\d*', '', glsl)
    glsl = re.sub(r'\bcbuffer\s+(\w+)', r'uniform \1', glsl)
    glsl = re.sub(r'\bTexture2D\b', 'sampler2D', glsl)
    return glsl

def dxbc_to_stub(source, stage):
    temp_regs, tex_count, cb_count, inst_count = 4, 0, 1, 0
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
    
    lines = ["#version 300 es", "precision highp float;",
             f"// Generated from {shader_model}, {inst_count} instructions", ""]
    
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
    
    lines.extend(["", "    r0 = u_data0[0];", "    r1 = r0 * u_data0[1];", "    r0 = r0 + r1;", ""])
    
    if stage == 'vertex':
        lines.extend(["    gl_Position = r0;", "    v_color = r0;"])
    else:
        if tex_count > 0:
            lines.append("    r0 = r0 * texture(u_tex0, v_color.xy);")
        lines.append("    fragColor = r0;")
    
    lines.append("}")
    return "\n".join(lines)

# ============== Mali Offline Compiler 调用 ==============
def analyze_spirv_direct(spirv_bytes, shader_type, shader_name, target_gpu=None):
    target_gpu = target_gpu or CONFIG.target_gpu
    if not os.path.exists(MALIOC_PATH):
        return {'error': f'malioc not found: {MALIOC_PATH}', 'success': False, 'name': shader_name, 'type': shader_type}
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.spv', delete=False) as f:
        f.write(bytes(spirv_bytes))
        spv_path = f.name
    
    try:
        stage_flag = '--vertex' if shader_type == 'vertex' else '--fragment'
        cmd = [MALIOC_PATH, '--format', 'json', '--core', target_gpu, stage_flag, spv_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            cmd = [MALIOC_PATH, '--format', 'json', '--core', target_gpu, spv_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {'error': result.stderr[:300], 'success': False, 'name': shader_name, 'type': shader_type}
        
        data = json.loads(result.stdout)
        parsed = parse_malioc(data, shader_name, shader_type)
        parsed['encoding'] = 'SPIRV'
        parsed['target_gpu'] = target_gpu
        return parsed
    except Exception as e:
        return {'error': str(e), 'success': False, 'name': shader_name, 'type': shader_type}
    finally:
        if os.path.exists(spv_path):
            os.unlink(spv_path)

def run_malioc(glsl, shader_type, shader_name, target_gpu=None):
    target_gpu = target_gpu or CONFIG.target_gpu
    if not os.path.exists(MALIOC_PATH):
        return {'error': f'malioc not found: {MALIOC_PATH}', 'success': False}
    
    suffix = '.vert' if shader_type == 'vertex' else '.frag'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(glsl)
        glsl_path = f.name
    
    try:
        stage_flag = '--vertex' if shader_type == 'vertex' else '--fragment'
        cmd = [MALIOC_PATH, '--format', 'json', '--core', target_gpu, stage_flag, glsl_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {'error': result.stderr[:300], 'success': False, 'name': shader_name, 'type': shader_type}
        
        data = json.loads(result.stdout)
        parsed = parse_malioc(data, shader_name, shader_type)
        parsed['target_gpu'] = target_gpu
        return parsed
    except Exception as e:
        return {'error': str(e), 'success': False, 'name': shader_name, 'type': shader_type}
    finally:
        if os.path.exists(glsl_path):
            os.unlink(glsl_path)

def parse_malioc(data, name, stype):
    result = {'name': name, 'type': stype, 'success': True, 'cycles': {}, 'registers': {}, 'bound': 'Unknown'}
    try:
        v = data['shaders'][0]['variants'][0]
        props = v.get('properties', [])
        perf = v.get('performance', {})
        
        for p in props:
            n = p.get('name', '')
            val = p.get('value', 0)
            if 'work_registers' in n:
                result['registers']['work'] = val
            elif 'uniform_registers' in n:
                result['registers']['uniform'] = val
            elif 'stack_spill' in n:
                result['registers']['stack_spilling'] = val
        
        pipelines = perf.get('pipelines', [])
        cycles = perf.get('shortest_path_cycles', {}).get('cycle_count', [])
        bound_list = perf.get('shortest_path_cycles', {}).get('bound_pipelines', [])
        
        cycle_map = {'A': 0, 'LS': 0, 'T': 0, 'V': 0}
        for i, pn in enumerate(pipelines):
            if i < len(cycles):
                pn_l = pn.lower()
                if 'arith' in pn_l and 'total' in pn_l:
                    cycle_map['A'] = cycles[i]
                elif 'load' in pn_l or 'store' in pn_l:
                    cycle_map['LS'] = cycles[i]
                elif 'tex' in pn_l:
                    cycle_map['T'] = cycles[i]
                elif 'vary' in pn_l:
                    cycle_map['V'] = cycles[i]
        
        result['cycles'] = {
            'arithmetic': cycle_map['A'], 'load_store': cycle_map['LS'],
            'texture': cycle_map['T'], 'varying': cycle_map['V'],
            'total': max(cycle_map.values()) if cycle_map.values() else 0
        }
        
        if bound_list:
            bn = bound_list[0].lower()
            if 'arith' in bn: result['bound'] = 'Arithmetic'
            elif 'load' in bn or 'store' in bn: result['bound'] = 'Load/Store'
            elif 'tex' in bn: result['bound'] = 'Texture'
            elif 'vary' in bn: result['bound'] = 'Varying'
            else: result['bound'] = bound_list[0]
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
    return result

# ============== 导出功能 ==============
def export_json(results: List[Dict], rdc_name: str, output_dir: str) -> str:
    """导出分析结果为 JSON"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mali_analysis_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    export_data = {
        'metadata': {
            'rdc_file': rdc_name,
            'target_gpu': CONFIG.target_gpu,
            'timestamp': datetime.now().isoformat(),
            'malioc_path': MALIOC_PATH,
            'total_shaders': len(results),
            'successful': sum(1 for r in results if r.get('success')),
        },
        'shaders': results
    }
    
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    return filepath

def export_csv(results: List[Dict], rdc_name: str, output_dir: str) -> str:
    """导出分析结果为 CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mali_analysis_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 表头
        writer.writerow([
            'Name', 'Type', 'Encoding', 'Target GPU', 'Bound',
            'Arith Cycles', 'LS Cycles', 'Tex Cycles', 'Vary Cycles', 'Total Cycles',
            'Work Regs', 'Uniform Regs', 'Stack Spill', 'Usage Count', 'Success', 'Error'
        ])
        
        for r in results:
            c = r.get('cycles', {})
            reg = r.get('registers', {})
            writer.writerow([
                r.get('name', ''), r.get('type', ''), r.get('encoding', ''),
                r.get('target_gpu', CONFIG.target_gpu), r.get('bound', ''),
                c.get('arithmetic', 0), c.get('load_store', 0),
                c.get('texture', 0), c.get('varying', 0), c.get('total', 0),
                reg.get('work', 0), reg.get('uniform', 0), reg.get('stack_spilling', 0),
                r.get('usage_count', 1), r.get('success', False), r.get('error', '')
            ])
    
    return filepath

def load_history(output_dir: str) -> List[Dict]:
    """加载历史分析记录"""
    history = []
    if not os.path.exists(output_dir):
        return history
    
    for f in os.listdir(output_dir):
        if f.startswith('mali_analysis_') and f.endswith('.json'):
            try:
                with open(os.path.join(output_dir, f), 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    history.append({
                        'filename': f,
                        'metadata': data.get('metadata', {}),
                        'shaders': data.get('shaders', [])
                    })
            except:
                pass
    
    # 按时间排序
    history.sort(key=lambda x: x['metadata'].get('timestamp', ''), reverse=True)
    return history

def compare_results(current: List[Dict], previous: List[Dict]) -> Dict:
    """对比两次分析结果"""
    comparison = {
        'improved': [],
        'regressed': [],
        'unchanged': [],
        'new': [],
        'removed': []
    }
    
    prev_map = {r['name']: r for r in previous if r.get('success')}
    curr_map = {r['name']: r for r in current if r.get('success')}
    
    for name, curr in curr_map.items():
        if name not in prev_map:
            comparison['new'].append(curr)
        else:
            prev = prev_map[name]
            curr_total = curr.get('cycles', {}).get('total', 0)
            prev_total = prev.get('cycles', {}).get('total', 0)
            
            if prev_total > 0:
                diff_pct = (curr_total - prev_total) / prev_total * 100
                if diff_pct < -5:
                    comparison['improved'].append({'shader': curr, 'prev_cycles': prev_total, 'diff_pct': diff_pct})
                elif diff_pct > 5:
                    comparison['regressed'].append({'shader': curr, 'prev_cycles': prev_total, 'diff_pct': diff_pct})
                else:
                    comparison['unchanged'].append(curr)
    
    for name in prev_map:
        if name not in curr_map:
            comparison['removed'].append(prev_map[name])
    
    return comparison

# ============== 优化建议生成 ==============
def generate_suggestions_html(results):
    suggestions = []
    
    for r in results:
        if not r.get('success'):
            continue
        
        bound = r.get('bound', '').lower()
        regs = r.get('registers', {})
        usage = r.get('usage_count', 1)
        name = r.get('name', 'Unknown')
        
        if 'arith' in bound:
            suggestions.append({'shader': name, 'priority': 'HIGH', 'category': 'Arithmetic',
                'title': 'Arithmetic Bound - 减少计算量',
                'description': '使用 mediump 精度、预计算常量、使用 LUT 替代复杂数学函数',
                'impact': '可减少 10-30% 算术周期'})
        elif 'tex' in bound:
            suggestions.append({'shader': name, 'priority': 'HIGH', 'category': 'Texture',
                'title': 'Texture Bound - 优化纹理采样',
                'description': '减少采样次数、使用 Mipmap、避免依赖采样',
                'impact': '可减少 20-40% 纹理周期'})
        elif 'load' in bound or 'store' in bound:
            suggestions.append({'shader': name, 'priority': 'HIGH', 'category': 'Memory',
                'title': 'Load/Store Bound - 优化内存访问',
                'description': '减少 Uniform 访问、合并数据到 vec4、使用 UBO',
                'impact': '可减少 15-25% 内存周期'})
        elif 'vary' in bound:
            suggestions.append({'shader': name, 'priority': 'HIGH', 'category': 'Varying',
                'title': 'Varying Bound - 优化数据传递',
                'description': '减少 Varying 数量、使用 flat 限定符、在 FS 重新计算简单值',
                'impact': '可减少 20-30% Varying 周期'})
        
        if regs.get('stack_spilling', 0) > 0:
            suggestions.insert(0, {'shader': name, 'priority': 'CRITICAL', 'category': 'Register',
                'title': f'寄存器溢出 ({regs["stack_spilling"]} bytes)',
                'description': '减少临时变量、使用 mediump、拆分 Shader',
                'impact': '消除溢出可提升 50%+ 性能'})
        
        if usage > 50:
            suggestions.insert(0, {'shader': name, 'priority': 'HIGH', 'category': 'General',
                'title': f'热点 Shader - 被 {usage} 个 Draw Call 使用',
                'description': '优先优化此 Shader，考虑合批减少 Draw Call',
                'impact': '优化此 Shader 将产生最大性能收益'})
    
    if not suggestions:
        return ''
    
    html = '''
    <h2 style="color:#f39c12;margin-top:40px;">🔧 Optimization Suggestions</h2>
    <div style="background:#16213e;border-radius:8px;padding:20px;margin-top:15px;">'''
    
    priority_colors = {'CRITICAL': '#ff6b6b', 'HIGH': '#f39c12', 'MEDIUM': '#4ecca3', 'LOW': '#888'}
    
    for s in suggestions[:15]:
        color = priority_colors.get(s['priority'], '#888')
        html += f'''
        <div style="margin-bottom:15px;padding:15px;background:#0f3460;border-radius:6px;border-left:4px solid {color};">
            <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;">
                <span style="background:{color};color:#000;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:bold;">{s['priority']}</span>
                <span style="color:#888;">{s['category']}</span>
                <span style="color:#4ecca3;">{s['shader']}</span>
            </div>
            <div style="font-weight:bold;color:#eee;margin-bottom:5px;">{s['title']}</div>
            <div style="color:#aaa;font-size:0.9em;">{s['description']}</div>
            <div style="color:#4ecca3;font-size:0.85em;margin-top:5px;">📈 {s['impact']}</div>
        </div>'''
    
    html += '</div>'
    return html

# ============== HTML 报告生成 ==============
def gen_html(results, rdc_name, output_path, comparison=None):
    target_gpu = CONFIG.target_gpu
    
    # GPU 选项 HTML
    gpu_options = ""
    for arch, gpus in SUPPORTED_GPUS.items():
        gpu_options += f'<optgroup label="{arch.replace("_", " ").title()}">'
        for gpu in gpus:
            selected = 'selected' if gpu == target_gpu else ''
            popular = '⭐ ' if gpu in POPULAR_GPUS else ''
            gpu_options += f'<option value="{gpu}" {selected}>{popular}{gpu}</option>'
        gpu_options += '</optgroup>'
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mali Shader Analysis - {rdc_name}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
        .card {{ background: #16213e; border-radius: 8px; padding: 20px; margin: 15px 0; border-left: 4px solid #00d4ff; transition: all 0.2s; }}
        .card:hover {{ transform: translateX(5px); box-shadow: 0 4px 12px rgba(0,212,255,0.2); }}
        .card.error {{ border-left-color: #ff6b6b; }}
        .card-header {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }}
        .name {{ font-size: 1.2em; font-weight: bold; color: #00d4ff; }}
        .type {{ color: #888; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px; }}
        .metric {{ background: #0f3460; padding: 15px; border-radius: 6px; }}
        .metric-label {{ color: #888; font-size: 0.85em; }}
        .metric-value {{ font-size: 1.5em; font-weight: bold; color: #4ecca3; margin-top: 5px; }}
        .bar {{ height: 20px; background: #0f3460; border-radius: 4px; margin: 5px 0; overflow: hidden; }}
        .fill {{ height: 100%; border-radius: 4px; }}
        .fill.a {{ background: linear-gradient(90deg, #ff6b6b, #ee5a24); }}
        .fill.ls {{ background: linear-gradient(90deg, #4ecca3, #38ada9); }}
        .fill.t {{ background: linear-gradient(90deg, #00d4ff, #0097e6); }}
        .fill.v {{ background: linear-gradient(90deg, #9b59b6, #8e44ad); }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }}
        .badge.arithmetic {{ background: #ff6b6b; color: #fff; }}
        .badge.texture {{ background: #00d4ff; color: #000; }}
        .badge.load-store {{ background: #4ecca3; color: #000; }}
        .badge.varying {{ background: #9b59b6; color: #fff; }}
        .badge.usage {{ background: #f39c12; color: #000; }}
        .badge.encoding {{ background: #2c3e50; color: #eee; }}
        .badge.gpu {{ background: #e74c3c; color: #fff; }}
        .summary {{ background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 30px; display: grid; grid-template-columns: repeat(6, 1fr); gap: 20px; text-align: center; }}
        .summary-value {{ font-size: 2em; font-weight: bold; color: #00d4ff; }}
        .summary-label {{ color: #888; margin-top: 5px; }}
        .error-msg {{ color: #ff6b6b; }}
        .eid-list {{ margin-top: 10px; padding: 10px; background: #0f3460; border-radius: 6px; display: none; }}
        .eid-list.show {{ display: block; }}
        .eid-item {{ display: inline-block; padding: 3px 8px; margin: 2px; background: #16213e; border-radius: 4px; font-size: 0.85em; color: #00d4ff; }}
        .eid-toggle {{ color: #888; font-size: 0.85em; margin-top: 8px; cursor: pointer; }}
        .eid-toggle:hover {{ color: #00d4ff; }}
        .filters {{ background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }}
        .filter-group {{ display: flex; align-items: center; gap: 8px; }}
        .filter-label {{ color: #888; font-size: 0.9em; }}
        select, input, button {{ background: #0f3460; border: 1px solid #00d4ff; color: #eee; padding: 8px 12px; border-radius: 4px; }}
        select:focus, input:focus {{ outline: none; border-color: #4ecca3; }}
        button {{ cursor: pointer; font-weight: bold; }}
        button:hover {{ background: #00d4ff; color: #000; }}
        .gpu-selector {{ background: #0f3460; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .gpu-selector h3 {{ margin: 0 0 10px 0; color: #00d4ff; }}
        .export-buttons {{ display: flex; gap: 10px; margin-top: 15px; }}
        .export-buttons button {{ background: #4ecca3; border-color: #4ecca3; color: #000; }}
        .comparison {{ background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .comparison h3 {{ color: #f39c12; margin-top: 0; }}
        .comparison-item {{ padding: 10px; margin: 5px 0; border-radius: 4px; }}
        .comparison-item.improved {{ background: rgba(78, 204, 163, 0.2); border-left: 3px solid #4ecca3; }}
        .comparison-item.regressed {{ background: rgba(255, 107, 107, 0.2); border-left: 3px solid #ff6b6b; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🎮 Mali Shader Analysis Report</h1>
    <p>RDC: <strong>{rdc_name}</strong> | Generated: <strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</strong></p>
    
    <div class="gpu-selector">
        <h3>🖥️ Target GPU</h3>
        <div style="display:flex;gap:15px;align-items:center;flex-wrap:wrap;">
            <select id="gpuSelect" style="min-width:200px;">
                {gpu_options}
            </select>
            <span class="badge gpu" id="currentGpu">{target_gpu}</span>
            <button onclick="alert('请在 RenderDoc Python Shell 中重新运行脚本并修改 CONFIG.target_gpu')">
                🔄 如何切换 GPU
            </button>
        </div>
        <div class="export-buttons">
            <button onclick="exportData('json')">📥 Export JSON</button>
            <button onclick="exportData('csv')">📊 Export CSV</button>
            <button onclick="showHistory()">📜 View History</button>
        </div>
    </div>
'''
    
    # 对比结果区域
    if comparison:
        html += '''<div class="comparison"><h3>📊 Comparison with Previous Analysis</h3>'''
        if comparison['improved']:
            html += '<h4 style="color:#4ecca3;">✅ Improved Shaders</h4>'
            for item in comparison['improved'][:5]:
                html += f'''<div class="comparison-item improved">
                    {item["shader"]["name"]}: {item["prev_cycles"]:.2f} → {item["shader"]["cycles"]["total"]:.2f} ({item["diff_pct"]:.1f}%)
                </div>'''
        if comparison['regressed']:
            html += '<h4 style="color:#ff6b6b;">⚠️ Regressed Shaders</h4>'
            for item in comparison['regressed'][:5]:
                html += f'''<div class="comparison-item regressed">
                    {item["shader"]["name"]}: {item["prev_cycles"]:.2f} → {item["shader"]["cycles"]["total"]:.2f} (+{item["diff_pct"]:.1f}%)
                </div>'''
        html += f'''<p style="color:#888;margin-top:15px;">New: {len(comparison["new"])} | Removed: {len(comparison["removed"])} | Unchanged: {len(comparison["unchanged"])}</p></div>'''
    
    success = sum(1 for r in results if r.get('success'))
    arith_total = sum(r.get('cycles', {}).get('arithmetic', 0) for r in results if r.get('success'))
    tex_total = sum(r.get('cycles', {}).get('texture', 0) for r in results if r.get('success'))
    total_draw_calls = sum(r.get('usage_count', 1) for r in results)
    max_cycles = max((r.get('cycles', {}).get('total', 0) for r in results if r.get('success')), default=0)
    
    html += f'''
    <div class="summary">
        <div><div class="summary-value">{len(results)}</div><div class="summary-label">Unique Shaders</div></div>
        <div><div class="summary-value">{success}</div><div class="summary-label">Analyzed</div></div>
        <div><div class="summary-value">{total_draw_calls}</div><div class="summary-label">Draw Calls</div></div>
        <div><div class="summary-value">{arith_total:.1f}</div><div class="summary-label">Total Arith Cycles</div></div>
        <div><div class="summary-value">{tex_total:.1f}</div><div class="summary-label">Total Tex Cycles</div></div>
        <div><div class="summary-value">{max_cycles:.1f}</div><div class="summary-label">Max Shader Cycles</div></div>
    </div>
    
    <div class="filters">
        <div class="filter-group">
            <span class="filter-label">Type:</span>
            <select id="filterType" onchange="filterShaders()">
                <option value="">All</option>
                <option value="vertex">Vertex</option>
                <option value="fragment">Fragment</option>
            </select>
        </div>
        <div class="filter-group">
            <span class="filter-label">Sort:</span>
            <select id="sortBy" onchange="sortShaders()">
                <option value="cycles">Cycles (High to Low)</option>
                <option value="usage">Usage Count</option>
                <option value="name">Name</option>
            </select>
        </div>
        <div class="filter-group">
            <span class="filter-label">Bound:</span>
            <select id="filterBound" onchange="filterShaders()">
                <option value="">All</option>
                <option value="Arithmetic">Arithmetic</option>
                <option value="Texture">Texture</option>
                <option value="Load/Store">Load/Store</option>
                <option value="Varying">Varying</option>
            </select>
        </div>
        <div class="filter-group">
            <span class="filter-label">Search:</span>
            <input type="text" id="searchInput" placeholder="Shader name..." onkeyup="filterShaders()">
        </div>
    </div>
    
    <div id="shaderList">
'''
    
    for r in results:
        cls = 'card' if r.get('success') else 'card error'
        shader_type = r.get('type', 'unknown')
        bound = r.get('bound', 'Unknown')
        cycles_total = r.get('cycles', {}).get('total', 0) if r.get('success') else 0
        usage_count = r.get('usage_count', 1)
        encoding = r.get('encoding', 'Unknown')
        
        html += f'''<div class="{cls}" data-type="{shader_type}" data-bound="{bound}" data-cycles="{cycles_total}" data-usage="{usage_count}" data-name="{r.get("name", "")}">
        <div class="card-header">
            <span class="name">{r.get("name", "?")}</span>
            <span class="type">({shader_type})</span>'''
        
        if r.get('success'):
            bound_css = bound.lower().replace('/', '-')
            html += f'''
            <span class="badge {bound_css}">{bound}</span>
            <span class="badge encoding">{encoding}</span>
            <span class="badge usage">Used: {usage_count}x</span>'''
        
        html += '</div>'
        
        if r.get('success'):
            c = r.get('cycles', {})
            mx = max(c.get('arithmetic', 1), c.get('texture', 1), c.get('load_store', 1), c.get('varying', 1), 0.01)
            html += '<div class="metrics">'
            for label, key, css in [('Arithmetic', 'arithmetic', 'a'), ('Load/Store', 'load_store', 'ls'), ('Texture', 'texture', 't'), ('Varying', 'varying', 'v')]:
                val = c.get(key, 0)
                pct = val / mx * 100 if mx > 0 else 0
                html += f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{val:.2f}</div><div class="bar"><div class="fill {css}" style="width:{pct}%"></div></div></div>'
            html += '</div>'
            
            regs = r.get('registers', {})
            if regs:
                html += f'<p style="margin-top:15px;color:#888;">Registers: Work={regs.get("work", "?")} | Uniform={regs.get("uniform", "?")}</p>'
            
            eids = r.get('used_by_eids', [])
            if eids:
                eid_display = eids[:20]
                more = len(eids) - 20 if len(eids) > 20 else 0
                html += f'''
                <div class="eid-toggle" onclick="this.nextElementSibling.classList.toggle('show')">
                    ▶ Show {len(eids)} Draw Calls using this shader
                </div>
                <div class="eid-list">'''
                for eid in eid_display:
                    html += f'<span class="eid-item">EID {eid}</span>'
                if more > 0:
                    html += f'<span class="eid-item">... +{more} more</span>'
                html += '</div>'
        else:
            html += f'<p class="error-msg">Error: {r.get("error", "?")}</p>'
        
        html += '</div>'
    
    html += generate_suggestions_html(results)
    
    # 将结果数据嵌入 JavaScript 供导出使用
    results_json = json.dumps(results, ensure_ascii=False)
    
    html += f'''</div>
    
    <script>
    const analysisData = {results_json};
    const rdcName = "{rdc_name}";
    const targetGpu = "{target_gpu}";
    
    function filterShaders() {{
        const typeFilter = document.getElementById('filterType').value;
        const boundFilter = document.getElementById('filterBound').value;
        const searchText = document.getElementById('searchInput').value.toLowerCase();
        const cards = document.querySelectorAll('.card');
        
        cards.forEach(card => {{
            const type = card.dataset.type;
            const bound = card.dataset.bound;
            const name = card.dataset.name.toLowerCase();
            const matchType = !typeFilter || type === typeFilter;
            const matchBound = !boundFilter || bound === boundFilter;
            const matchSearch = !searchText || name.includes(searchText);
            card.style.display = (matchType && matchBound && matchSearch) ? 'block' : 'none';
        }});
    }}
    
    function sortShaders() {{
        const sortBy = document.getElementById('sortBy').value;
        const container = document.getElementById('shaderList');
        const cards = Array.from(container.querySelectorAll('.card'));
        
        cards.sort((a, b) => {{
            if (sortBy === 'cycles') {{
                return parseFloat(b.dataset.cycles) - parseFloat(a.dataset.cycles);
            }} else if (sortBy === 'usage') {{
                return parseInt(b.dataset.usage) - parseInt(a.dataset.usage);
            }} else {{
                return a.dataset.name.localeCompare(b.dataset.name);
            }}
        }});
        
        cards.forEach(card => container.appendChild(card));
    }}
    
    function exportData(format) {{
        const data = {{
            metadata: {{
                rdc_file: rdcName,
                target_gpu: targetGpu,
                timestamp: new Date().toISOString(),
                total_shaders: analysisData.length
            }},
            shaders: analysisData
        }};
        
        let content, filename, mimeType;
        
        if (format === 'json') {{
            content = JSON.stringify(data, null, 2);
            filename = 'mali_analysis_' + new Date().toISOString().slice(0,19).replace(/[:-]/g,'') + '.json';
            mimeType = 'application/json';
        }} else {{
            // CSV
            const headers = ['Name','Type','Encoding','Bound','Arith','LS','Tex','Vary','Total','WorkRegs','Usage'];
            const rows = analysisData.map(r => [
                r.name, r.type, r.encoding || '', r.bound || '',
                (r.cycles?.arithmetic || 0).toFixed(2),
                (r.cycles?.load_store || 0).toFixed(2),
                (r.cycles?.texture || 0).toFixed(2),
                (r.cycles?.varying || 0).toFixed(2),
                (r.cycles?.total || 0).toFixed(2),
                r.registers?.work || 0,
                r.usage_count || 1
            ]);
            content = [headers.join(','), ...rows.map(r => r.join(','))].join('\\n');
            filename = 'mali_analysis_' + new Date().toISOString().slice(0,19).replace(/[:-]/g,'') + '.csv';
            mimeType = 'text/csv';
        }}
        
        const blob = new Blob([content], {{ type: mimeType }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }}
    
    function showHistory() {{
        alert('历史记录功能:\\n\\n分析结果已自动保存到 output 目录。\\n\\n查看历史：在 output 文件夹中找到 mali_analysis_*.json 文件。\\n\\n对比功能：在 Python Shell 中运行 compare_with_history() 函数。');
    }}
    </script>
</div></body></html>'''
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path

# ============== 单 Shader 分析 ==============
def analyze_single_shader(controller, pipe, reflection, stage, eid, target, target_gpu=None):
    import renderdoc as rd
    
    name = f"{'VS' if stage == 'vertex' else 'PS'}_EID{eid}"
    encoding = get_encoding_name(reflection.encoding) if hasattr(reflection, 'encoding') else 'Unknown'
    target_gpu = target_gpu or CONFIG.target_gpu
    
    print(f"  [{stage.upper()}] {name}: encoding={encoding}")
    
    if encoding in ['SPIRV', 'OpenGLSPIRV']:
        if hasattr(reflection, 'rawBytes') and len(reflection.rawBytes) > 0:
            print(f"    -> SPIR-V direct ({len(reflection.rawBytes)} bytes)")
            return analyze_spirv_direct(reflection.rawBytes, stage, name, target_gpu)
    
    try:
        disasm = controller.DisassembleShader(pipe, reflection, target)
        if disasm and len(disasm) > 50:
            fmt = detect_format(disasm)
            print(f"    -> Disasm: {fmt}, {len(disasm)} chars")
            
            if fmt == 'GLSL':
                glsl = disasm
            elif fmt == 'HLSL':
                glsl = hlsl_to_glsl(disasm, stage)
            else:
                glsl = dxbc_to_stub(disasm, stage)
            
            r = run_malioc(glsl, stage, name, target_gpu)
            r['encoding'] = fmt
            return r
    except Exception as e:
        print(f"    -> Disasm failed: {e}")
    
    return {'name': name, 'type': stage, 'success': False, 'error': 'No shader data available'}

# ============== 主分析函数 ==============
def analyze_current_capture(target_gpu=None, save_exports=True):
    """
    分析当前打开的 RDC 中的 Shader
    
    Args:
        target_gpu: 目标 GPU 型号，如 "Mali-G78"、"Mali-G710" 等
        save_exports: 是否保存 JSON/CSV 导出文件
    """
    import renderdoc as rd
    
    if target_gpu:
        CONFIG.target_gpu = target_gpu
    
    ctx = pyrenderdoc.GetCaptureContext()
    if not ctx:
        print("[ERROR] No capture context available")
        print("Please open an RDC file first!")
        return
    
    controller = ctx.GetReplayController()
    if not controller:
        print("[ERROR] No replay controller")
        return
    
    rdc_path = ctx.GetCaptureFilename()
    rdc_name = os.path.basename(rdc_path) if rdc_path else "unknown"
    
    print("=" * 60)
    print(f"  Mali Shader Analyzer v2.0")
    print("=" * 60)
    print(f"  RDC File: {rdc_name}")
    print(f"  Target GPU: {CONFIG.target_gpu}")
    print(f"  Max Shaders: {CONFIG.max_shaders}")
    print("=" * 60)
    print("")
    
    targets = controller.GetDisassemblyTargets(True)
    target = targets[0] if targets else None
    if not target:
        print("[ERROR] No disassembly target")
        return
    
    actions = controller.GetRootActions()
    
    def find_draws(action_list):
        result = []
        for a in action_list:
            if a.flags & rd.ActionFlags.Drawcall:
                result.append(a)
            if len(a.children) > 0:
                result.extend(find_draws(a.children))
        return result
    
    draws = find_draws(actions)
    print(f"[INFO] Found {len(draws)} draw calls")
    print("")
    
    results = []
    analyzed_ids = set()
    shader_to_eids = {}
    shader_to_info = {}
    
    for dc in draws:
        if len(analyzed_ids) >= CONFIG.max_shaders * 2:
            print(f"[INFO] Reached max shader limit ({CONFIG.max_shaders * 2})")
            break
        
        eid = dc.eventId
        controller.SetFrameEvent(eid, True)
        state = controller.GetPipelineState()
        pipe = state.GetGraphicsPipelineObject()
        
        for stage, shader_stage in [('vertex', rd.ShaderStage.Vertex), ('fragment', rd.ShaderStage.Pixel)]:
            try:
                refl = state.GetShaderReflection(shader_stage)
                if refl:
                    rid = refl.resourceId.id() if hasattr(refl.resourceId, 'id') else refl.resourceId
                    if rid not in shader_to_eids:
                        shader_to_eids[rid] = []
                    shader_to_eids[rid].append(eid)
                    
                    if rid not in analyzed_ids:
                        r = analyze_single_shader(controller, pipe, refl, stage, eid, target)
                        if r:
                            r['resource_id'] = rid
                            results.append(r)
                            shader_to_info[rid] = len(results) - 1
                            analyzed_ids.add(rid)
            except Exception as e:
                print(f"  [{stage.upper()} Error] EID {eid}: {e}")
    
    for rid, eids in shader_to_eids.items():
        if rid in shader_to_info:
            idx = shader_to_info[rid]
            results[idx]['used_by_eids'] = eids
            results[idx]['usage_count'] = len(eids)
    
    # 加载历史并对比
    comparison = None
    if CONFIG.compare_history:
        history = load_history(OUTPUT_DIR)
        if history:
            prev = history[0]['shaders']
            comparison = compare_results(results, prev)
            print(f"[INFO] Compared with previous analysis: {history[0]['filename']}")
    
    # 生成报告
    report_path = os.path.join(OUTPUT_DIR, "mali_shader_report.html")
    gen_html(results, rdc_name, report_path, comparison)
    
    # 保存导出文件
    json_path = csv_path = None
    if save_exports:
        if CONFIG.save_json:
            json_path = export_json(results, rdc_name, OUTPUT_DIR)
        if CONFIG.save_csv:
            csv_path = export_csv(results, rdc_name, OUTPUT_DIR)
    
    print("")
    print("=" * 60)
    print(f"  ✅ Analysis Complete")
    print("=" * 60)
    print(f"  Analyzed: {len(results)} unique shaders")
    print(f"  Target GPU: {CONFIG.target_gpu}")
    print(f"  Report: {report_path}")
    if json_path:
        print(f"  JSON Export: {json_path}")
    if csv_path:
        print(f"  CSV Export: {csv_path}")
    print("=" * 60)
    
    # Top 10
    print("\nTop 10 by Cycles:")
    sorted_results = sorted([r for r in results if r.get('success')], 
                           key=lambda x: x.get('cycles', {}).get('total', 0), 
                           reverse=True)[:10]
    for i, r in enumerate(sorted_results, 1):
        c = r.get('cycles', {})
        print(f"  {i}. {r['name']}: {c.get('total', 0):.2f} cyc (Bound: {r.get('bound', '?')})")
    
    return results

# ============== 便捷函数 ==============
def set_gpu(gpu_name: str):
    """设置目标 GPU"""
    all_gpus = []
    for gpus in SUPPORTED_GPUS.values():
        all_gpus.extend(gpus)
    
    if gpu_name not in all_gpus:
        print(f"[ERROR] Unknown GPU: {gpu_name}")
        print(f"[INFO] Supported GPUs: {', '.join(POPULAR_GPUS[:5])}...")
        print(f"[INFO] Run list_gpus() to see all supported GPUs")
        return
    
    CONFIG.target_gpu = gpu_name
    print(f"[OK] Target GPU set to: {gpu_name}")

def list_gpus():
    """列出所有支持的 GPU"""
    print("\n=== Supported Mali GPUs ===\n")
    for arch, gpus in SUPPORTED_GPUS.items():
        print(f"{arch.replace('_', ' ').title()}:")
        for gpu in gpus:
            star = "⭐ " if gpu in POPULAR_GPUS else "   "
            current = " (current)" if gpu == CONFIG.target_gpu else ""
            print(f"  {star}{gpu}{current}")
        print("")

def compare_with_history(index: int = 0):
    """与历史分析结果对比"""
    history = load_history(OUTPUT_DIR)
    if not history:
        print("[INFO] No history found")
        return
    
    if index >= len(history):
        print(f"[ERROR] Invalid index. Available: 0-{len(history)-1}")
        return
    
    print(f"\n=== History Entry {index} ===")
    meta = history[index]['metadata']
    print(f"  File: {history[index]['filename']}")
    print(f"  RDC: {meta.get('rdc_file', '?')}")
    print(f"  GPU: {meta.get('target_gpu', '?')}")
    print(f"  Time: {meta.get('timestamp', '?')}")
    print(f"  Shaders: {meta.get('total_shaders', '?')}")

def show_history():
    """显示历史分析记录"""
    history = load_history(OUTPUT_DIR)
    if not history:
        print("[INFO] No history found in", OUTPUT_DIR)
        return
    
    print(f"\n=== Analysis History ({len(history)} records) ===\n")
    for i, h in enumerate(history[:10]):
        meta = h['metadata']
        print(f"  [{i}] {h['filename']}")
        print(f"      RDC: {meta.get('rdc_file', '?')} | GPU: {meta.get('target_gpu', '?')}")
        print(f"      Time: {meta.get('timestamp', '?')[:19]}")
        print("")

# ============== 执行 ==============
print("""
╔══════════════════════════════════════════════════════════════╗
║        Mali Shader Analyzer v2.0 for RenderDoc               ║
╠══════════════════════════════════════════════════════════════╣
║  Commands:                                                   ║
║    analyze_current_capture()     - Analyze current RDC       ║
║    analyze_current_capture("Mali-G710")  - Use specific GPU  ║
║    set_gpu("Mali-G78")           - Change target GPU         ║
║    list_gpus()                   - List all supported GPUs   ║
║    show_history()                - Show analysis history     ║
╚══════════════════════════════════════════════════════════════╝
""")