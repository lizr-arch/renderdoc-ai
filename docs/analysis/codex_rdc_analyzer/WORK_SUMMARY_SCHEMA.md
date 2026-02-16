# WORK_SUMMARY_SCHEMA — Schema / Pipeline / Bridge

- WHAT: 统一输出口径的 Schema、Pipeline State 深度采样与 Bridge 方案。
- WHY: 防止“双 schema”与数据不一致导致的结论失真。
- HOW: 迁移相关设计与实现细节，保留 WHAT/WHY/HOW。

---

## 2. Canonical Schema v1.0（统一输出格式）

为了让分析结果可被 compare、前端、自动化消费，我们定义了统一的 JSON Schema：

```json
{
  "schema_version": "1.0",
  "meta": {
    "capture_file": "game.rdc",
    "analyzer_version": "0.9.0",
    "timestamp": "2025-01-21T15:00:00Z",
    "platform": "Vulkan"
  },
  "summary": {
    "total_draw_calls": 1234,
    "total_triangles": 567890,
    "total_textures": 45,
    "total_vram_mb": 128.5,
    "issue_count": { "high": 3, "medium": 7, "low": 12 }
  },
  "coverage": {
    "overall": "high",
    "details": {
      "textures": "present",
      "draw_calls": "present",
      "pipeline_state": "partial",
      "resource_lifecycle": "estimated",
      "markers": "missing"
    },
    "confidence_reasons": ["Markers 未启用，Pass 边界使用启发式推断"],
    "sampling_stats": { "pipeline_samples": 15, "total_draw_calls": 1234 }
  },
  "data_richness": {
    "baseline": {
      "events": ["eventId", "outputs", "children"],
      "textures": ["resourceId", "byteSize", "msSamp"],
      "pipeline_state": ["PipeState", "API-specific state"]
    },
    "routes": {
      "A": {
        "source": "xml",
        "coverage": "partial",
        "events": { "present": [], "partial": [], "missing": [] },
        "textures": { "present": [], "partial": [], "missing": [] },
        "pipeline_state": { "status": "requires_replay" }
      },
      "C": {
        "source": "compare",
        "coverage": "summary_only",
        "events": { "status": "summary_only" },
        "textures": { "status": "summary_only" },
        "pipeline_state": { "status": "summary_only" }
      }
    },
    "notes": ["A/C 不伪造字段，仅声明缺口"],
    "baseline_source": "docs/analysis/codex_rdc_analyzer/2025-01-31-rdc-analyzer-data-richness-baseline.md"
  },
  "events": [...],
  "draw_calls": [...],
  "resources": {
    "textures": [...],
    "buffers": [...]
  },
  "issues": [
    {
      "code": "RD_001",
      "severity": "high",
      "category": "performance",
      "message": "Draw Call 数量过多 (1234 > 500)",
      "event_ids": [100, 200, 300],
      "resource_ids": [],
      "evidence": { "actual": 1234, "threshold": 500 },
      "suggestion": "使用 GPU Instancing 或 Static Batching"
    }
  ],
  "suggestions": [
    {
      "id": "SUG_RD_001",
      "title": "减少 Draw Call 数量",
      "priority": "high",
      "steps": ["启用 GPU Instancing", "合并相同材质的网格"],
      "expected_impact": { "draw_calls": "-30% to -50%" },
      "risk": "low",
      "engine_howto": {
        "unity": "Edit > Project Settings > Player > Static Batching",
        "unreal": "Enable Instanced Rendering"
      },
      "verification_plan": {
        "metrics": ["Draw Call Count"],
        "expected_direction": "decrease",
        "how_to_capture": "相同场景再次抓帧"
      }
    }
  ],
  "preflight": {
    "status": "warning",
    "missing_data": [
      { "item": "Debug Markers", "impact": "无法识别 Pass 边界", "severity": "medium" }
    ],
    "capture_recommendations": [
      {
        "action": "启用 Debug Markers",
        "unity": "确保 FrameDebugger 打开",
        "unreal": "启用 RenderDoc 插件"
      }
    ],
    "degraded_conclusions": ["Pass 结构分析使用启发式推断"]
  }
}
```

**关键代码入口**：
- `main.py:AnalysisPipeline._export_reports()` — 构建并导出 JSON
- `main.py:AnalysisPipeline._build_coverage_report()` — 构建 coverage 块
- `main.py:AnalysisPipeline._build_data_richness()` — 构建 data_richness 块
- `main.py:AnalysisPipeline._build_preflight()` — 构建 preflight 块
- `main.py:AnalysisPipeline._build_suggestions()` — 构建 suggestions 块

---


## 3. Pipeline State 采样器（P0-NEW-4）

### 3.1 问题背景

分析每个 Draw Call 的 Pipeline State 代价太高（上千次 `SetFrameEvent` + `GetPipelineState`），需要智能采样。

### 3.2 解决方案

创建 `extractors/pipeline_sampler.py`，支持 4 种采样策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `UNIFORM` | 均匀间隔采样（每 k 个取 1） | 一般场景 |
| `DIVERSE` | 按 VS/PS 签名去重采样 | 保证覆盖所有 Shader 组合 |
| `FIRST_N` | 前 N 个 Draw Call | 初始化阶段分析 |
| `LAST_N` | 后 N 个 Draw Call | 最终输出阶段分析 |

**关键代码**：
```python
# extractors/pipeline_sampler.py
class SamplingStrategy(Enum):
    UNIFORM = "uniform"
    DIVERSE = "diverse"
    FIRST_N = "first_n"
    LAST_N = "last_n"

def sample_pipeline_states(
    controller,
    events: List[ActionDescription],
    sample_count: int = 5,
    strategy: SamplingStrategy = SamplingStrategy.UNIFORM
) -> PipelineSamplingResult:
    """
    从 Draw Call 列表中采样并提取 Pipeline State。
    
    返回:
        PipelineSamplingResult: 包含采样的 snapshots 和统计信息
    """
    if strategy == SamplingStrategy.DIVERSE:
        picked = _pick_diverse(events, sample_count)
    elif strategy == SamplingStrategy.UNIFORM:
        picked = _pick_uniform(events, sample_count)
    # ...
    
    snapshots = []
    for event in picked:
        controller.SetFrameEvent(event.eventId, True)
        state = controller.GetPipelineState()
        snapshots.append(_extract_snapshot(state, event.eventId))
    
    return PipelineSamplingResult(
        snapshots=snapshots,
        total_events=len(events),
        sampled_count=len(snapshots),
        strategy=strategy.value
    )
```

**数据结构**：
```python
@dataclass
class PipelineSnapshot:
    event_id: int
    vertex_shader: str  # Shader 资源 ID
    pixel_shader: str
    topology: str  # "TriangleList", "LineStrip", etc.
    viewports: List[Dict]
    scissor_rects: List[Dict]
    blend_state: Optional[Dict]
    depth_stencil_state: Optional[Dict]
    rasterizer_state: Optional[Dict]
    render_targets: List[str]
    depth_target: Optional[str]
```

**集成到主管线**：
```python
# main.py:AnalysisPipeline._sample_pipeline_states()
def _sample_pipeline_states(self):
    from extractors.pipeline_sampler import sample_pipeline_states, SamplingStrategy
    
    strategy = SamplingStrategy(self.options.pipeline_sample_strategy)
    self._pipeline_sampling_result = sample_pipeline_states(
        controller=self._controller,
        events=self._draw_calls,
        sample_count=self.options.pipeline_sample_count,
        strategy=strategy,
    )
```

---


## 4. Schema Bridge（P0-NEW-2）

### 4.1 问题背景

`compare` 命令需要消费 `analyze` 的 JSON 输出，但 JSON 格式（Canonical Schema v1）与 `DiffEngine` 期望的 `CaptureData` 格式不同。

### 4.2 解决方案

在 `parsers/rdc_loader.py` 中实现 Schema Bridge：

```python
# parsers/rdc_loader.py
def _convert_schema_v1_to_capture_data(json_data: Dict) -> CaptureData:
    """
    将 Canonical Schema v1.0 的 JSON 转换为 DiffEngine 期望的 CaptureData 格式。
    
    关键转换:
    - json_data['resources']['textures'] → CaptureData.textures
    - json_data['draw_calls'] → CaptureData.draw_calls
    - json_data['summary'] → CaptureData.stats
    """
    textures = []
    for tex in json_data.get('resources', {}).get('textures', []):
        textures.append(TextureInfo(
            resourceId=tex.get('resourceId') or tex.get('id'),
            name=tex.get('name', ''),
            width=tex.get('width', 0),
            height=tex.get('height', 0),
            # ...
        ))
    
    # ... 类似处理 draw_calls, buffers, shaders ...
    
    return CaptureData(
        textures=textures,
        draw_calls=draw_calls,
        # ...
    )

def load_capture_file(path: str, ...) -> CaptureData:
    """统一加载入口，支持 .rdc, .xml, .json"""
    if path.endswith('.json'):
        data = json.load(open(path))
        if data.get('schema_version') == '1.0':
            return _convert_schema_v1_to_capture_data(data)
    # ...
```

### 4.3 集成测试

`tests/test_schema_bridge_integration.py` 验证端到端链路：

```python
def test_bridge_preserves_texture_diff():
    """验证纹理差异不会被 Bridge 丢失"""
    baseline = create_schema_v1_json(textures=[
        {"resourceId": "T1", "width": 512, "height": 512}
    ])
    target = create_schema_v1_json(textures=[
        {"resourceId": "T1", "width": 1024, "height": 1024}  # 尺寸变化
    ])
    
    baseline_data = load_capture_file(baseline)
    target_data = load_capture_file(target)
    
    diff = DiffEngine().compare(baseline_data, target_data)
    
    assert len(diff.texture_changes) > 0
    assert diff.texture_changes[0].field == 'width'
```

---
