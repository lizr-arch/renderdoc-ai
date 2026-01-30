#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 对比测试脚本
================

测试文件:
  - g145.rdc (基准)
  - g145-battle-2.rdc (对比)

使用方法:
  1. 在 RenderDoc 中打开 g145.rdc
  2. Python Shell 中运行: exec(open(r'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\compare_test.py').read())
  3. 执行: analyze_baseline()
  
  4. 关闭，打开 g145-battle-2.rdc
  5. 再次加载此脚本
  6. 执行: analyze_and_compare()
"""

import subprocess
import tempfile
import json
import os
import re
from datetime import datetime

# ============== 配置 ==============
MALIOC_PATH = r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe"
OUTPUT_DIR = r"d:\Code\git\renderdoc\scripts\rdc_analyzer\output"
TARGET_GPU = "Mali-G78"  # Pixel 9 可能是 G715/G720，但 G78 兼容性好

# 测试文件路径
BASELINE_RDC = r"D:\renderdoc\goog pixel-9\g145.rdc"
COMPARE_RDC = r"D:\renderdoc\goog pixel-9\g145-battle-2.rdc"

# ============== 核心函数 ==============
def detect_format(source):
    if re.search(r'#version\s+\d+', source):
        return 'GLSL'
    if re.search(r'\bcbuffer\b', source) or re.search(r':\s*SV_\w+', source):
        return 'HLSL'
    return 'UNKNOWN'

def analyze_spirv_direct(spirv_bytes, shader_type, shader_name):
    if not os.path.exists(MALIOC_PATH):
        return {'error': 'malioc not found', 'success': False, 'name': shader_name, 'type': shader_type}
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.spv', delete=False) as f:
        f.write(bytes(spirv_bytes))
        spv_path = f.name
    
    try:
        stage_flag = '--vertex' if shader_type == 'vertex' else '--fragment'
        cmd = [MALIOC_PATH, '--format', 'json', '--core', TARGET_GPU, stage_flag, spv_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {'error': result.stderr[:200], 'success': False, 'name': shader_name, 'type': shader_type}
        
        data = json.loads(result.stdout)
        return parse_malioc(data, shader_name, shader_type)
    except Exception as e:
        return {'error': str(e), 'success': False, 'name': shader_name, 'type': shader_type}
    finally:
        if os.path.exists(spv_path):
            os.unlink(spv_path)

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
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
    return result

def analyze_current_rdc(max_shaders=50):
    """分析当前打开的 RDC"""
    import renderdoc as rd
    
    ctx = pyrenderdoc.GetCaptureContext()
    if not ctx:
        print("[ERROR] No capture context")
        return None, None
    
    controller = ctx.GetReplayController()
    rdc_path = ctx.GetCaptureFilename()
    rdc_name = os.path.basename(rdc_path) if rdc_path else "unknown"
    
    print(f"\n{'='*50}")
    print(f"  Analyzing: {rdc_name}")
    print(f"  Target GPU: {TARGET_GPU}")
    print(f"{'='*50}\n")
    
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
    
    results = []
    analyzed_ids = set()
    shader_to_eids = {}
    
    for dc in draws[:max_shaders * 5]:
        if len(analyzed_ids) >= max_shaders * 2:
            break
        
        eid = dc.eventId
        controller.SetFrameEvent(eid, True)
        state = controller.GetPipelineState()
        
        for stage, shader_stage in [('vertex', rd.ShaderStage.Vertex), ('fragment', rd.ShaderStage.Pixel)]:
            try:
                refl = state.GetShaderReflection(shader_stage)
                if refl:
                    rid = refl.resourceId.id() if hasattr(refl.resourceId, 'id') else refl.resourceId
                    if rid not in shader_to_eids:
                        shader_to_eids[rid] = []
                    shader_to_eids[rid].append(eid)
                    
                    if rid not in analyzed_ids:
                        encoding = str(refl.encoding) if hasattr(refl, 'encoding') else 'Unknown'
                        
                        if 'SPIRV' in encoding or 'OpenGLSPIRV' in encoding:
                            if hasattr(refl, 'rawBytes') and len(refl.rawBytes) > 0:
                                name = f"{'VS' if stage == 'vertex' else 'PS'}_EID{eid}"
                                r = analyze_spirv_direct(refl.rawBytes, stage, name)
                                r['resource_id'] = rid
                                r['encoding'] = 'SPIRV'
                                results.append(r)
                                analyzed_ids.add(rid)
                                print(f"  [{stage.upper()}] {name}: {r.get('cycles', {}).get('total', 0):.2f} cyc")
            except Exception as e:
                pass
    
    # 添加使用计数
    for r in results:
        rid = r.get('resource_id')
        if rid in shader_to_eids:
            r['usage_count'] = len(shader_to_eids[rid])
    
    print(f"\n[OK] Analyzed {len(results)} unique shaders")
    return results, rdc_name

def save_results(results, rdc_name, label):
    """保存分析结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"compare_{label}.json")
    
    data = {
        'rdc_file': rdc_name,
        'label': label,
        'target_gpu': TARGET_GPU,
        'timestamp': datetime.now().isoformat(),
        'shaders': results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"[SAVED] {filepath}")
    return filepath

def load_baseline():
    """加载基准数据"""
    filepath = os.path.join(OUTPUT_DIR, "compare_baseline.json")
    if not os.path.exists(filepath):
        print(f"[ERROR] Baseline not found: {filepath}")
        print("[INFO] Please run analyze_baseline() first")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_comparison_report(baseline, current, output_path):
    """生成对比报告"""
    
    baseline_map = {r['name']: r for r in baseline['shaders'] if r.get('success')}
    current_map = {r['name']: r for r in current['shaders'] if r.get('success')}
    
    improved = []
    regressed = []
    unchanged = []
    new_shaders = []
    
    for name, curr in current_map.items():
        curr_total = curr.get('cycles', {}).get('total', 0)
        
        if name in baseline_map:
            base = baseline_map[name]
            base_total = base.get('cycles', {}).get('total', 0)
            
            if base_total > 0:
                diff = curr_total - base_total
                diff_pct = diff / base_total * 100
                
                item = {
                    'name': name,
                    'type': curr.get('type'),
                    'base_cycles': base_total,
                    'curr_cycles': curr_total,
                    'diff': diff,
                    'diff_pct': diff_pct,
                    'usage': curr.get('usage_count', 1)
                }
                
                if diff_pct < -5:
                    improved.append(item)
                elif diff_pct > 5:
                    regressed.append(item)
                else:
                    unchanged.append(item)
        else:
            new_shaders.append({
                'name': name,
                'cycles': curr_total,
                'usage': curr.get('usage_count', 1)
            })
    
    # 按影响排序
    improved.sort(key=lambda x: x['diff_pct'])
    regressed.sort(key=lambda x: x['diff_pct'], reverse=True)
    
    # 计算总结
    total_base = sum(baseline_map[n]['cycles']['total'] * baseline_map[n].get('usage_count', 1) 
                     for n in baseline_map)
    total_curr = sum(current_map[n]['cycles']['total'] * current_map[n].get('usage_count', 1) 
                     for n in current_map)
    total_diff_pct = (total_curr - total_base) / total_base * 100 if total_base > 0 else 0
    
    # 生成 HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mali Shader Comparison Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        h2 {{ color: #f39c12; margin-top: 30px; }}
        .summary {{ background: #16213e; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; }}
        .summary-value {{ font-size: 2em; font-weight: bold; }}
        .summary-label {{ color: #888; margin-top: 5px; }}
        .improved {{ color: #4ecca3; }}
        .regressed {{ color: #ff6b6b; }}
        .unchanged {{ color: #888; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        tr:hover {{ background: #16213e; }}
        .diff-pos {{ color: #ff6b6b; }}
        .diff-neg {{ color: #4ecca3; }}
        .files {{ background: #0f3460; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.85em; }}
        .badge.vs {{ background: #3498db; }}
        .badge.ps {{ background: #9b59b6; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🔄 Mali Shader Comparison Report</h1>
    
    <div class="files">
        <p><strong>Baseline:</strong> {baseline['rdc_file']}</p>
        <p><strong>Current:</strong> {current['rdc_file']}</p>
        <p><strong>Target GPU:</strong> {TARGET_GPU}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
    
    <div class="summary">
        <div class="summary-grid">
            <div>
                <div class="summary-value {'improved' if total_diff_pct < 0 else 'regressed'}">{total_diff_pct:+.1f}%</div>
                <div class="summary-label">Total Cycle Change</div>
            </div>
            <div>
                <div class="summary-value improved">{len(improved)}</div>
                <div class="summary-label">Improved Shaders</div>
            </div>
            <div>
                <div class="summary-value regressed">{len(regressed)}</div>
                <div class="summary-label">Regressed Shaders</div>
            </div>
            <div>
                <div class="summary-value unchanged">{len(unchanged)}</div>
                <div class="summary-label">Unchanged</div>
            </div>
        </div>
    </div>
'''
    
    if regressed:
        html += '''
    <h2>⚠️ Regressed Shaders (Performance Decreased)</h2>
    <table>
        <tr><th>Shader</th><th>Type</th><th>Baseline</th><th>Current</th><th>Change</th><th>Usage</th></tr>
'''
        for item in regressed[:20]:
            badge = 'vs' if item['type'] == 'vertex' else 'ps'
            html += f'''
        <tr>
            <td>{item['name']}</td>
            <td><span class="badge {badge}">{item['type'].upper()}</span></td>
            <td>{item['base_cycles']:.2f}</td>
            <td>{item['curr_cycles']:.2f}</td>
            <td class="diff-pos">+{item['diff_pct']:.1f}%</td>
            <td>{item['usage']}x</td>
        </tr>'''
        html += '</table>'
    
    if improved:
        html += '''
    <h2>✅ Improved Shaders (Performance Increased)</h2>
    <table>
        <tr><th>Shader</th><th>Type</th><th>Baseline</th><th>Current</th><th>Change</th><th>Usage</th></tr>
'''
        for item in improved[:20]:
            badge = 'vs' if item['type'] == 'vertex' else 'ps'
            html += f'''
        <tr>
            <td>{item['name']}</td>
            <td><span class="badge {badge}">{item['type'].upper()}</span></td>
            <td>{item['base_cycles']:.2f}</td>
            <td>{item['curr_cycles']:.2f}</td>
            <td class="diff-neg">{item['diff_pct']:.1f}%</td>
            <td>{item['usage']}x</td>
        </tr>'''
        html += '</table>'
    
    if new_shaders:
        html += f'''
    <h2>🆕 New Shaders (Not in Baseline)</h2>
    <p>Found {len(new_shaders)} new shaders in current capture.</p>
'''
    
    html += '''
</div>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path

# ============== 用户接口 ==============
def analyze_baseline():
    """
    Step 1: 分析基准 RDC (g145.rdc)
    请先在 RenderDoc 中打开 g145.rdc，然后运行此函数
    """
    results, rdc_name = analyze_current_rdc(max_shaders=50)
    if results:
        save_results(results, rdc_name, 'baseline')
        print("\n" + "="*50)
        print("✅ Baseline analysis complete!")
        print("="*50)
        print("\nNext steps:")
        print("1. Close this RDC")
        print("2. Open g145-battle-2.rdc")
        print("3. Run: analyze_and_compare()")
    return results

def analyze_and_compare():
    """
    Step 2: 分析当前 RDC 并与基准对比
    请先在 RenderDoc 中打开 g145-battle-2.rdc，然后运行此函数
    """
    baseline = load_baseline()
    if not baseline:
        return None
    
    results, rdc_name = analyze_current_rdc(max_shaders=50)
    if not results:
        return None
    
    save_results(results, rdc_name, 'current')
    
    current = {
        'rdc_file': rdc_name,
        'shaders': results
    }
    
    report_path = os.path.join(OUTPUT_DIR, "comparison_report.html")
    generate_comparison_report(baseline, current, report_path)
    
    print("\n" + "="*50)
    print("✅ Comparison complete!")
    print("="*50)
    print(f"\nReport: {report_path}")
    
    # 打印摘要
    baseline_map = {r['name']: r for r in baseline['shaders'] if r.get('success')}
    current_map = {r['name']: r for r in results if r.get('success')}
    
    improved = regressed = 0
    for name in current_map:
        if name in baseline_map:
            base_t = baseline_map[name]['cycles']['total']
            curr_t = current_map[name]['cycles']['total']
            if base_t > 0:
                diff = (curr_t - base_t) / base_t * 100
                if diff < -5: improved += 1
                elif diff > 5: regressed += 1
    
    print(f"\nSummary:")
    print(f"  Improved: {improved}")
    print(f"  Regressed: {regressed}")
    print(f"  Common shaders: {len(set(baseline_map.keys()) & set(current_map.keys()))}")
    
    return results

# ============== 启动提示 ==============
print("""
╔══════════════════════════════════════════════════════════════╗
║           RDC Comparison Test Script                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  测试文件:                                                   ║
║    Baseline: g145.rdc                                        ║
║    Compare:  g145-battle-2.rdc                               ║
║                                                              ║
║  使用步骤:                                                   ║
║                                                              ║
║  Step 1: 打开 g145.rdc                                       ║
║          运行: analyze_baseline()                            ║
║                                                              ║
║  Step 2: 打开 g145-battle-2.rdc                              ║
║          运行: analyze_and_compare()                         ║
║                                                              ║
║  报告将保存到: output/comparison_report.html                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
