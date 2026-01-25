# Phase 1: 性能分析激活计划

> **目标**: 将现有的 `PerformanceAnalyzer` 和 `OptimizationAdvisor` 与 HTML 报告系统连接
> **预计时间**: 2-3 天
> **并行任务数**: 3 个独立任务

---

## 📊 当前架构问题

```
断裂点:
parse_rdc_xml.py ──→ [dict] ──→ generate_real_report.py ──→ HTML
                       ↓
                   ❌ 没有进入
                       ↓
               AnalysisContext ──→ PerformanceAnalyzer ──→ Issues
```

## 🎯 目标架构

```
parse_rdc_xml.py ──→ [dict] ──→ XMLToContextBridge ──→ AnalysisContext
                                                              ↓
                                                    ┌─────────┴─────────┐
                                                    ↓                   ↓
                                           PerformanceAnalyzer   OptimizationAdvisor
                                                    ↓                   ↓
                                                 Issues           OptimizationReport
                                                    ↓                   ↓
                                                    └─────────┬─────────┘
                                                              ↓
                                                   generate_real_report.py
                                                              ↓
                                                    HTML (含性能洞察面板)
```

---

## 🚀 并行任务分配

### ═══════════════════════════════════════════════════════════
### 任务 A: XMLToContextBridge 桥接器
### ═══════════════════════════════════════════════════════════

**负责人**: AI-A
**依赖**: 无 (独立任务)
**输出**: `scripts/rdc_analyzer/core/xml_bridge.py`

#### A.1 创建桥接器类

**文件**: `scripts/rdc_analyzer/core/xml_bridge.py`

> ⚠️ **重要**: 下方代码已根据 `core/types.py` 和 `core/context.py` 的实际字段名进行调整

```python
#!/usr/bin/env python3
"""
XML 解析结果到 AnalysisContext 的桥接器

将 parse_rdc_xml.py 的输出转换为 AnalysisContext 对象，
使其能够被 PerformanceAnalyzer 等分析器处理。
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

# 导入现有类型 (注意: 使用 types.py 中的实际字段名)
from .types import (
    TextureInfo, BufferInfo, ShaderInfo, PassInfo,
    DrawCallInfo, FrameSummary, ParsedData
)
from .context import AnalysisContext


class XMLToContextBridge:
    """将 XML 解析的 dict 数据转换为 AnalysisContext"""
    
    def __init__(self, xml_data: Dict[str, Any], rdc_path: str = ""):
        """
        Args:
            xml_data: parse_rdc_xml.py 返回的字典
            rdc_path: 原始 RDC 文件路径
        """
        self.xml_data = xml_data
        self.rdc_path = rdc_path
        self.context: Optional[AnalysisContext] = None
    
    def convert(self) -> AnalysisContext:
        """执行转换，返回 AnalysisContext"""
        # 创建 ParsedData
        parsed = ParsedData(
            file_path=self.rdc_path,
            api=self.xml_data.get('api', 'D3D11'),
            textures=self.xml_data.get('textures', []),
            buffers=self.xml_data.get('buffers', []),
            shaders=self.xml_data.get('shaders', []),
        )
        
        self.context = AnalysisContext(parsed=parsed)
        
        # 1. 转换纹理
        self._convert_textures()
        
        # 2. 转换缓冲区
        self._convert_buffers()
        
        # 3. 转换着色器
        self._convert_shaders()
        
        # 4. 转换 DrawCall/Pass
        self._convert_events()
        
        # 5. 计算帧摘要
        self._compute_frame_summary()
        
        return self.context
    
    def _convert_textures(self):
        """转换纹理数据 (匹配 TextureInfo 字段)"""
        textures = self.xml_data.get('textures', [])
        for tex_dict in textures:
            tex_info = TextureInfo(
                resource_id=str(tex_dict.get('id', '')),
                name=tex_dict.get('name', ''),
                width=tex_dict.get('width', 0),
                height=tex_dict.get('height', 0),
                depth=tex_dict.get('depth', 1),
                array_size=tex_dict.get('arrayLayers', 1),
                mip_levels=tex_dict.get('mips', 1),  # 注意: types.py 用 mip_levels
                format=tex_dict.get('format', ''),
                format_category=self._get_format_category(tex_dict.get('format', '')),
                memory_size=self._estimate_texture_size(tex_dict),
                is_render_target=tex_dict.get('isRT', False),
                is_depth_stencil=tex_dict.get('isDepth', False),
            )
            self.context.textures.append(tex_info)
    
    def _convert_buffers(self):
        """转换缓冲区数据 (匹配 BufferInfo 字段)"""
        buffers = self.xml_data.get('buffers', [])
        for buf_dict in buffers:
            # 推断 usage 列表
            usage_list = self._infer_buffer_usage(buf_dict)
            
            buf_info = BufferInfo(
                resource_id=str(buf_dict.get('id', '')),
                name=buf_dict.get('name', ''),
                size=buf_dict.get('length', 0),  # 注意: types.py 用 size
                usage=usage_list,
                stride=buf_dict.get('stride', 0),
                is_constant_buffer='ConstantBuffer' in str(usage_list),
            )
            self.context.buffers.append(buf_info)
    
    def _convert_shaders(self):
        """转换着色器数据 (匹配 ShaderInfo 字段)"""
        # 从 shaders 列表
        shaders = self.xml_data.get('shaders', [])
        for shader_dict in shaders:
            shader_info = ShaderInfo(
                resource_id=str(shader_dict.get('id', '')),
                type=shader_dict.get('type', ''),  # VS | PS | CS
                name=shader_dict.get('name', ''),
                stage=shader_dict.get('stage', ''),
                entry_point=shader_dict.get('entryPoint', 'main'),
            )
            self.context.shaders.append(shader_info)
        
        # 也从 pipelineState 中提取 (如果有)
        pipeline_state = self.xml_data.get('pipelineState', {})
        shader_stages = ['VS', 'PS', 'GS', 'HS', 'DS', 'CS']
        existing_ids = {s.resource_id for s in self.context.shaders}
        
        for stage in shader_stages:
            shader_data = pipeline_state.get(stage, {})
            if shader_data and shader_data.get('resourceId'):
                res_id = str(shader_data.get('resourceId'))
                if res_id not in existing_ids:
                    shader_info = ShaderInfo(
                        resource_id=res_id,
                        type=stage,
                        name=shader_data.get('name', f'{stage}_Shader'),
                        stage=stage,
                        entry_point=shader_data.get('entryPoint', 'main'),
                    )
                    self.context.shaders.append(shader_info)
                    existing_ids.add(res_id)
    
    def _convert_events(self):
        """转换事件/DrawCall 数据 (匹配 DrawCallInfo 和 PassInfo 字段)"""
        actions = self.xml_data.get('actions', [])
        
        current_pass: Optional[PassInfo] = None
        pass_index = 0
        
        for action in actions:
            # 检测 Pass 边界 (通过 RT 切换)
            if self._is_pass_boundary(action, current_pass):
                if current_pass:
                    current_pass.end_event_id = action.get('eventId', 0) - 1
                    self.context.passes.append(current_pass)
                current_pass = PassInfo(
                    index=pass_index,  # 注意: types.py 用 index
                    name=f"Pass_{pass_index}",
                    start_event_id=action.get('eventId', 0),
                )
                pass_index += 1
            
            # 创建 DrawCall 信息
            flags = action.get('flags', {})
            if flags.get('drawcall') or flags.get('dispatch'):
                dc_info = DrawCallInfo(
                    event_id=action.get('eventId', 0),
                    type='Draw' if flags.get('drawcall') else 'Dispatch',
                    index_count=action.get('numIndices', 0),
                    vertex_count=action.get('numVerts', 0),
                    instance_count=action.get('numInstances', 1),
                    pass_index=pass_index - 1 if pass_index > 0 else 0,
                    rt_ids=[str(o.get('resourceId', '')) for o in action.get('outputs', []) if isinstance(o, dict)],
                )
                self.context.draw_calls.append(dc_info)
                
                # 更新 Pass 统计
                if current_pass:
                    if flags.get('drawcall'):
                        current_pass.draw_count += 1
                        current_pass.total_vertices += dc_info.vertex_count or dc_info.index_count
                    elif flags.get('dispatch'):
                        current_pass.dispatch_count += 1
        
        # 添加最后一个 Pass
        if current_pass:
            if actions:
                current_pass.end_event_id = actions[-1].get('eventId', 0)
            self.context.passes.append(current_pass)
    
    def _compute_frame_summary(self):
        """计算帧摘要 (匹配 FrameSummary 字段)"""
        summary = self.context.frame_summary
        
        summary.draw_call_count = sum(1 for dc in self.context.draw_calls if dc.type == 'Draw')
        summary.dispatch_count = sum(1 for dc in self.context.draw_calls if dc.type == 'Dispatch')
        summary.vertex_count = sum(dc.vertex_count or dc.index_count for dc in self.context.draw_calls)
        summary.primitive_count = summary.vertex_count // 3
        summary.texture_count = len(self.context.textures)
        summary.buffer_count = len(self.context.buffers)
        summary.pass_count = len(self.context.passes)
        summary.total_texture_memory = sum(t.memory_size for t in self.context.textures)
        summary.total_buffer_memory = sum(b.size for b in self.context.buffers)
    
    # === 辅助方法 ===
    
    def _estimate_texture_size(self, tex: Dict) -> int:
        """估算纹理大小 (字节)"""
        BPP_MAP = {
            'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
            'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
            'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5,
            'BC3_UNORM': 1, 'BC3_SRGB': 1,
            'BC7_UNORM': 1, 'BC7_SRGB': 1,
            'R8_UNORM': 1, 'R16_FLOAT': 2, 'R32_FLOAT': 4,
            'D24_UNORM_S8_UINT': 4, 'D32_FLOAT': 4, 'D32_FLOAT_S8X24_UINT': 8,
        }
        fmt = tex.get('format', 'R8G8B8A8_UNORM')
        bpp = BPP_MAP.get(fmt, 4)
        w = tex.get('width', 0)
        h = tex.get('height', 0)
        d = tex.get('depth', 1)
        layers = tex.get('arrayLayers', 1)
        mips = tex.get('mips', 1)
        
        base = w * h * d * layers * bpp
        if mips > 1:
            base = int(base * 1.33)
        return int(base)
    
    def _get_format_category(self, fmt: str) -> str:
        """获取格式类别"""
        if not fmt:
            return 'unknown'
        if fmt.startswith('BC') or 'ASTC' in fmt or 'ETC' in fmt:
            return 'compressed'
        if 'D16' in fmt or 'D24' in fmt or 'D32' in fmt:
            return 'depth'
        return 'uncompressed'
    
    def _infer_buffer_usage(self, buf: Dict) -> List[str]:
        """推断缓冲区用途"""
        usage = []
        flags = buf.get('creationFlags', [])
        flags_str = str(flags).lower()
        
        if 'vertex' in flags_str or 'vb' in flags_str:
            usage.append('VertexBuffer')
        if 'index' in flags_str or 'ib' in flags_str:
            usage.append('IndexBuffer')
        if 'constant' in flags_str or 'cb' in flags_str:
            usage.append('ConstantBuffer')
        if 'structured' in flags_str:
            usage.append('StructuredBuffer')
        if 'uav' in flags_str or 'unordered' in flags_str:
            usage.append('UAV')
        
        return usage if usage else ['Unknown']
    
    def _is_pass_boundary(self, action: Dict, current_pass: Optional[PassInfo]) -> bool:
        """检测是否为 Pass 边界"""
        name = action.get('name', '')
        if 'SetRenderTarget' in name or 'OMSetRenderTargets' in name:
            return True
        if 'BeginRenderPass' in name:
            return True
        if current_pass is None:
            return True
        return False
```

#### A.2 更新 `core/__init__.py`

在 `scripts/rdc_analyzer/core/__init__.py` 中添加导出:

```python
from .xml_bridge import XMLToContextBridge
```

#### A.3 单元测试

**文件**: `scripts/rdc_analyzer/tests/test_xml_bridge.py`

```python
#!/usr/bin/env python3
"""XMLToContextBridge 单元测试"""

import unittest
from core.xml_bridge import XMLToContextBridge


class TestXMLToContextBridge(unittest.TestCase):
    
    def test_empty_data(self):
        bridge = XMLToContextBridge({})
        ctx = bridge.convert()
        self.assertEqual(len(ctx.textures), 0)
        self.assertEqual(len(ctx.buffers), 0)
    
    def test_texture_conversion(self):
        data = {
            'textures': [
                {'id': 1, 'name': 'Diffuse', 'width': 1024, 'height': 1024,
                 'format': 'BC7_UNORM', 'mips': 10}
            ]
        }
        bridge = XMLToContextBridge(data)
        ctx = bridge.convert()
        self.assertEqual(len(ctx.textures), 1)
        self.assertEqual(ctx.textures[0].name, 'Diffuse')
        self.assertEqual(ctx.textures[0].width, 1024)
    
    def test_buffer_conversion(self):
        data = {
            'buffers': [
                {'id': 10, 'name': 'VB0', 'length': 65536,
                 'creationFlags': ['VertexBuffer']}
            ]
        }
        bridge = XMLToContextBridge(data)
        ctx = bridge.convert()
        self.assertEqual(len(ctx.buffers), 1)
        self.assertEqual(ctx.buffers[0].buffer_type, 'VertexBuffer')


if __name__ == '__main__':
    unittest.main()
```

#### A.4 验收标准

- [x] `XMLToContextBridge` 类可以从 XML dict 创建 `AnalysisContext`
- [x] 纹理、缓冲区、着色器正确转换
- [x] DrawCall 和 Pass 信息正确提取
- [x] 基础指标 (total_draw_calls, texture_memory 等) 正确计算
- [x] 单元测试全部通过 (16/16 passed ✅)

> **任务 A (TASK-007) 完成** - 验证人: Flux-0119, 时间: 2025-01-20

---

### ═══════════════════════════════════════════════════════════
### 任务 B: PerformanceAnalyzer 集成
### ═══════════════════════════════════════════════════════════

**负责人**: AI-B
**依赖**: 任务 A 完成后可测试，但可先开发
**输出**: 修改 `generate_real_report.py` + HTML 模板更新

#### B.1 修改 generate_real_report.py

**文件**: `scripts/rdc_analyzer/generate_real_report.py`

在现有代码中添加分析器调用:

```python
# === 在文件顶部添加导入 ===
from core.xml_bridge import XMLToContextBridge
from analyzers.performance_analyzer import PerformanceAnalyzer
from analyzers.base import AnalyzerPipeline

# === 在 generate_report 函数中添加 ===

def generate_report(xml_data: Dict, rdc_path: str, output_path: str):
    """生成 HTML 报告 (增强版: 含性能分析)"""
    
    # 1. 原有逻辑保持不变...
    
    # 2. 新增: 创建 AnalysisContext
    bridge = XMLToContextBridge(xml_data, rdc_path)
    context = bridge.convert()
    
    # 3. 新增: 运行性能分析
    pipeline = AnalyzerPipeline()
    perf_analyzer = PerformanceAnalyzer()
    pipeline.add_analyzer(perf_analyzer)
    
    analysis_result = pipeline.run(context)
    
    # 4. 提取性能洞察
    performance_insights = {
        'overall_score': perf_analyzer.report.overall_score,
        'issues': [issue.to_dict() for issue in perf_analyzer.report.issues],
        'metrics': {
            'shader_changes': perf_analyzer.report.metrics.get('shader_changes', 0),
            'rt_switches': perf_analyzer.report.metrics.get('rt_switches', 0),
            'small_batches': perf_analyzer.report.metrics.get('small_batches', 0),
        }
    }
    
    # 5. 传递给 HTML 模板
    html_content = render_html_template(
        xml_data=xml_data,
        performance_insights=performance_insights,  # 新增
        # ...其他参数
    )
    
    # 写入文件...
```

#### B.2 添加 HTML 性能洞察面板

**位置**: `generate_real_report.py` 的 HTML 模板部分

```html
<!-- 性能洞察面板 (插入到现有面板之后) -->
<div class="panel performance-panel">
    <div class="panel-header">
        <span class="icon">⚡</span>
        <span>性能洞察</span>
        <span class="score-badge" style="background: ${getScoreColor(performance_insights.overall_score)}">
            ${performance_insights.overall_score}/100
        </span>
    </div>
    <div class="panel-content">
        <!-- 关键指标 -->
        <div class="metrics-row">
            <div class="metric-item">
                <span class="metric-value">${performance_insights.metrics.shader_changes}</span>
                <span class="metric-label">Shader 切换</span>
            </div>
            <div class="metric-item">
                <span class="metric-value">${performance_insights.metrics.rt_switches}</span>
                <span class="metric-label">RT 切换</span>
            </div>
            <div class="metric-item">
                <span class="metric-value">${performance_insights.metrics.small_batches}</span>
                <span class="metric-label">小批次</span>
            </div>
        </div>
        
        <!-- 问题列表 -->
        <div class="issues-list">
            ${performance_insights.issues.map(issue => `
                <div class="issue-item severity-${issue.severity.toLowerCase()}">
                    <span class="issue-code">${issue.code}</span>
                    <span class="issue-message">${issue.message}</span>
                    <span class="issue-impact">影响: ${issue.impact_score}</span>
                </div>
            `).join('')}
        </div>
    </div>
</div>
```

#### B.3 添加 CSS 样式

```css
/* 性能洞察面板样式 */
.performance-panel {
    border-left: 4px solid #667eea;
}

.score-badge {
    padding: 4px 12px;
    border-radius: 12px;
    color: white;
    font-weight: bold;
}

.metrics-row {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
}

.metric-item {
    text-align: center;
    padding: 12px;
    background: #f8f9fa;
    border-radius: 8px;
    flex: 1;
}

.metric-value {
    display: block;
    font-size: 24px;
    font-weight: bold;
    color: #333;
}

.metric-label {
    font-size: 12px;
    color: #666;
}

.issue-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 4px;
}

.issue-item.severity-high { background: #fee2e2; }
.issue-item.severity-medium { background: #fef3c7; }
.issue-item.severity-low { background: #dbeafe; }

.issue-code {
    font-family: monospace;
    font-weight: bold;
    color: #444;
}

.issue-impact {
    margin-left: auto;
    font-size: 12px;
    color: #666;
}
```

#### B.4 验收标准

- [x] `generate_real_report.py` 成功调用 `XMLToContextBridge`
- [x] `PerformanceAnalyzer` 在报告生成时运行
- [x] HTML 报告中显示 "性能洞察" 面板
- [x] 面板显示 overall_score 和关键指标
- [x] 问题列表按严重程度着色显示
- [x] 单元测试全部通过 (23/23 passed ✅)

> **任务 B (TASK-008) 完成** - 验证人: Flux-0119, 时间: 2025-01-20

---

### ═══════════════════════════════════════════════════════════
### 任务 C: OptimizationAdvisor 集成
### ═══════════════════════════════════════════════════════════

**负责人**: Flux-0119 (认领于 2025-01-20)
**状态**: 🔄 进行中
**依赖**: 无 (独立任务)
**输出**: 新增优化建议生成脚本 + HTML 面板

#### C.1 创建优化建议生成入口

**文件**: `scripts/rdc_analyzer/generate_optimization_report.py`

```python
#!/usr/bin/env python3
"""
生成纹理优化建议报告

从 RDC XML 数据生成 Markdown 格式的优化建议。
可独立运行或集成到 HTML 报告中。

用法:
    python generate_optimization_report.py <rdc_xml_path> [-o output.md]
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

from core.optimization_advisor import OptimizationAdvisor, generate_optimization_report


def load_xml_data(xml_path: str) -> Dict[str, Any]:
    """加载 XML/JSON 解析结果"""
    path = Path(xml_path)
    if path.suffix == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 假设已有 parse_rdc_xml 模块
        from parse_rdc_xml import parse_rdc_xml
        return parse_rdc_xml(xml_path)


def main():
    parser = argparse.ArgumentParser(description='生成纹理优化建议报告')
    parser.add_argument('input', help='RDC XML 或 JSON 文件路径')
    parser.add_argument('-o', '--output', help='输出 Markdown 文件路径')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    
    args = parser.parse_args()
    
    # 加载数据
    data = load_xml_data(args.input)
    rdc_name = Path(args.input).stem
    
    # 提取纹理列表
    textures = data.get('textures', [])
    
    # 生成报告
    advisor = OptimizationAdvisor(
        textures=textures,
        rdc_name=rdc_name,
        # 可选: 传入去重和热度分析结果
        duplicate_analysis=data.get('duplicate_analysis'),
        usage_analysis=data.get('usage_analysis')
    )
    
    report = advisor.analyze()
    
    if args.json:
        output = json.dumps({
            'rdc_name': report.rdc_name,
            'generated_at': report.generated_at,
            'total_savings_bytes': report.get_total_savings(),
            'items': [item.to_dict() for item in report.items]
        }, ensure_ascii=False, indent=2)
    else:
        output = report.to_markdown()
    
    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"报告已保存到: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
```

#### C.2 添加到 HTML 报告的优化建议面板

在 `generate_real_report.py` 中添加:

```python
# 在 generate_report 函数中
from core.optimization_advisor import OptimizationAdvisor

def generate_report(...):
    # ... 现有代码 ...
    
    # 生成优化建议
    advisor = OptimizationAdvisor(
        textures=xml_data.get('textures', []),
        rdc_name=Path(rdc_path).stem
    )
    opt_report = advisor.analyze()
    
    optimization_data = {
        'total_savings_mb': opt_report.get_total_savings() / (1024 * 1024),
        'item_count': len(opt_report.items),
        'critical_count': sum(1 for i in opt_report.items if i.priority.name == 'CRITICAL'),
        'high_count': sum(1 for i in opt_report.items if i.priority.name == 'HIGH'),
        'items': [item.to_dict() for item in opt_report.items[:10]]  # 前10条
    }
    
    # 传递给模板...
```

#### C.3 HTML 优化建议面板

```html
<!-- 优化建议面板 -->
<div class="panel optimization-panel">
    <div class="panel-header">
        <span class="icon">💡</span>
        <span>优化建议</span>
        <span class="savings-badge">
            可节省 ${optimization_data.total_savings_mb.toFixed(1)} MB
        </span>
    </div>
    <div class="panel-content">
        <div class="opt-summary">
            <span class="opt-count">${optimization_data.item_count} 条建议</span>
            ${optimization_data.critical_count > 0 ? 
                `<span class="critical-badge">🔴 ${optimization_data.critical_count} 关键</span>` : ''}
            ${optimization_data.high_count > 0 ? 
                `<span class="high-badge">🟠 ${optimization_data.high_count} 高优</span>` : ''}
        </div>
        
        <div class="opt-list">
            ${optimization_data.items.map(item => `
                <div class="opt-item priority-${item.priority.toLowerCase()}">
                    <div class="opt-title">${item.title}</div>
                    <div class="opt-desc">${item.description}</div>
                    ${item.estimated_savings_bytes > 0 ? 
                        `<div class="opt-savings">可节省 ${(item.estimated_savings_bytes/1024/1024).toFixed(2)} MB</div>` : ''}
                </div>
            `).join('')}
        </div>
    </div>
</div>
```

#### C.4 验收标准

- [ ] `generate_optimization_report.py` 可独立运行
- [ ] 支持 JSON 和 Markdown 两种输出格式
- [ ] HTML 报告中显示 "优化建议" 面板
- [ ] 面板显示总节省量和建议数量
- [ ] 建议按优先级排序和着色

---

## 📋 任务依赖图

```
     ┌─────────┐
     │ 任务 A  │ XMLToContextBridge
     └────┬────┘
          │
          ▼ (提供 AnalysisContext)
     ┌─────────┐
     │ 任务 B  │ PerformanceAnalyzer 集成
     └─────────┘
     
     ┌─────────┐
     │ 任务 C  │ OptimizationAdvisor 集成 (独立)
     └─────────┘
```

**并行策略**:
- A 和 C 可完全并行
- B 需要 A 的输出，但可以先开发骨架代码，最后集成测试

---

## ✅ 整体验收标准

1. **运行命令**:
   ```bash
   py -3 scripts/rdc_analyzer/generate_real_report.py test.xml -o report.html
   ```

2. **验证项**:
   - [ ] HTML 报告正常生成
   - [ ] "性能洞察" 面板显示 overall_score
   - [ ] "优化建议" 面板显示建议列表
   - [ ] 控制台无 Python 错误

3. **代码质量**:
   - [ ] 所有新文件有文档注释
   - [ ] 函数有类型注解
   - [ ] 遵循项目 4 空格缩进

---

## 📁 涉及文件清单

| 任务 | 文件 | 操作 |
|------|------|------|
| A | `scripts/rdc_analyzer/core/xml_bridge.py` | 新建 |
| A | `scripts/rdc_analyzer/core/__init__.py` | 修改 |
| A | `scripts/rdc_analyzer/tests/test_xml_bridge.py` | 新建 |
| B | `scripts/rdc_analyzer/generate_real_report.py` | 修改 |
| C | `scripts/rdc_analyzer/generate_optimization_report.py` | 新建 |
| C | `scripts/rdc_analyzer/generate_real_report.py` | 修改 |

---

*计划创建时间: 2025-01-20*
*预计完成时间: 2025-01-22*
