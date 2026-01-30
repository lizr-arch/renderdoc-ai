# Agent B 任务文档：修复 3 + 修复 4

> **创建时间**: 2025-01-21  
> **分配者**: Agent A (Codex)  
> **执行者**: Agent B  
> **状态**: ✅ 已完成并验收  
> **验收者**: Agent A  
> **验收时间**: 2025-01-21  
> **最终测试**: 466 passed, 8 skipped

---

## 📋 任务概览

| 任务 | 文件 | 优先级 | 预估时间 |
|------|------|--------|----------|
| 修复 3: 禁止伪 DrawCallDetail | `main.py` | ⭐⭐⭐ | 15-20 分钟 |
| 修复 4: analysis.json bridge | `rdc_loader.py` | ⭐⭐⭐ | 15-20 分钟 |

**总预估**: 30-40 分钟

---

## ✅ 完成检查表（Agent B 勾选）

### 修复 3
- [x] 阅读并理解当前伪数据生成代码
- [x] 修改代码：缺失时输出 `missing/estimated` 而非假数据
- [x] 运行测试：`py -3 -m pytest tests -q --ignore=tests/test_audit.py`
- [x] Git 提交

### 修复 4  
- [x] 阅读并理解 `rdc_loader.py` 加载逻辑
- [x] 添加 schema_version 检测 + 转换逻辑
- [x] 新增至少 1 个测试用例 → 实际新增 15 个测试 (`test_schema_bridge.py`)
- [x] 运行测试：`py -3 -m pytest tests -q -k "loader or compare"`
- [x] Git 提交

### 最终验证
- [x] 全量测试：`cd scripts/rdc_analyzer && py -3 -m pytest tests -q` → **466 passed, 8 skipped**
- [x] 通知 Agent A 验收 → **Agent A 验收通过 ✅**

---

## 🔧 修复 3: 禁止伪 DrawCallDetail

### 问题描述

`main.py:1051-1102` 使用 `type()` 动态创建假的 `DrawCallDetail` 和 `ResourceLifetime` 对象，破坏了"A-first 可信闭环"的核心原则。

### 当前问题代码位置

```
文件: scripts/rdc_analyzer/main.py
行号: 1051-1102 (大约)
```

### 需要找到的代码模式

搜索以下关键字：
```bash
rg -n "type\(" scripts/rdc_analyzer/main.py | head -20
rg -n "DrawCallDetail" scripts/rdc_analyzer/main.py
rg -n "first_event\|last_event\|read_count" scripts/rdc_analyzer/main.py
```

### 修复方案

**原则**: 宁可输出 "数据缺失"，也不造假数据。

**方案 A（推荐）**: 缺失时返回带状态标记的对象

```python
# 修改前（伪代码示意）
DrawCallDetail = type('DrawCallDetail', (), {
    'vertex_count': 0,
    'instance_count': 0,
    ...
})

# 修改后
draw_call_detail = {
    'status': 'missing',  # 或 'estimated'
    'reason': 'Pipeline state not captured for this event',
    'confidence': 0.0,
    # 可选：提供估算值但明确标记
    'estimated_values': {
        'vertex_count': None,
        'instance_count': None,
    }
}
```

**方案 B**: 直接跳过，不输出该字段

```python
# 如果没有真实数据，直接不输出 draw_call_detail 字段
if has_real_pipeline_state:
    output['draw_call_detail'] = real_detail
# else: 不输出，让消费者知道这个字段可能不存在
```

### 验证方式

1. 运行测试确保不破坏现有功能：
   ```bash
   cd scripts/rdc_analyzer
   py -3 -m pytest tests -q --ignore=tests/test_audit.py
   ```

2. 检查输出 JSON/HTML 不含 `type(` 动态生成的假数据

### Git 提交模板

```bash
git add scripts/rdc_analyzer/main.py
git commit -m "fix(rdc-analyzer): 移除伪 DrawCallDetail/ResourceLifetime (P0-2)

- 删除 type() 动态创建假数据的代码
- 缺失数据时输出 status: missing/estimated
- 保持 HTML 渲染兼容（显示'数据未采集'）

审计修复: P0-2 真实 state 未贯通"
```

---

## 🔧 修复 4: analysis.json → CaptureData bridge

### 问题描述

`analyze` 命令输出的 JSON 使用 `schema_version=1.0` 格式，但 `compare` 命令的 `DiffEngine` 期望的是 `CaptureData` 格式（`textures/shaders/buffers` 列表）。两者不兼容导致无法直接对比。

### 当前问题代码位置

```
文件: scripts/rdc_analyzer/parsers/rdc_loader.py
行号: 258-265 (大约)
```

### 格式差异

**analyze 输出 (schema_version=1.0)**:
```json
{
  "schema_version": "1.0",
  "meta": {...},
  "resources": {
    "textures": {...},
    "buffers": {...}
  },
  "events": [...],
  "statistics": {...}
}
```

**compare/DiffEngine 期望 (CaptureData)**:
```json
{
  "textures": [...],    // 列表格式
  "shaders": [...],
  "buffers": [...],
  "events": [...],
  "statistics": {...}
}
```

### 修复方案

在 `rdc_loader.py` 的 `load_capture_file()` 或 JSON 加载分支中，检测并转换：

```python
def _convert_schema_v1_to_capture_data(data: dict) -> dict:
    """将 Canonical Schema v1.0 转换为 CaptureData 格式"""
    
    # 检测是否为 schema v1.0
    if data.get('schema_version') != '1.0':
        return data  # 不是 v1.0，原样返回
    
    # 转换资源格式
    resources = data.get('resources', {})
    
    # textures: dict → list
    textures_dict = resources.get('textures', {})
    textures_list = []
    for tex_id, tex_info in textures_dict.items():
        tex_entry = {
            'id': tex_id,
            'name': tex_info.get('name', ''),
            'width': tex_info.get('width', 0),
            'height': tex_info.get('height', 0),
            'format': tex_info.get('format', ''),
            'size_bytes': tex_info.get('size_bytes', 0),
            'mips': tex_info.get('mips', 1),
            # 保留原始数据
            **tex_info
        }
        textures_list.append(tex_entry)
    
    # buffers: dict → list
    buffers_dict = resources.get('buffers', {})
    buffers_list = []
    for buf_id, buf_info in buffers_dict.items():
        buf_entry = {
            'id': buf_id,
            'name': buf_info.get('name', ''),
            'size_bytes': buf_info.get('size_bytes', 0),
            **buf_info
        }
        buffers_list.append(buf_entry)
    
    # shaders: 如果存在
    shaders_dict = resources.get('shaders', {})
    shaders_list = list(shaders_dict.values()) if isinstance(shaders_dict, dict) else []
    
    # 构建 CaptureData 格式
    capture_data = {
        'textures': textures_list,
        'buffers': buffers_list,
        'shaders': shaders_list,
        'events': data.get('events', []),
        'statistics': data.get('summary', {}),  # summary → statistics
        # 保留元数据
        '_source_schema': '1.0',
        '_meta': data.get('meta', {}),
    }
    
    return capture_data
```

### 调用位置

在 `rdc_loader.py` 的 JSON 加载分支调用：

```python
# 找到类似这样的代码
elif file_ext == '.json':
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 新增：检测并转换 schema v1.0
    data = _convert_schema_v1_to_capture_data(data)
    
    return data
```

### 新增测试

在 `tests/test_rdc_loader.py` 或新建 `tests/test_schema_bridge.py`：

```python
def test_schema_v1_to_capture_data_conversion():
    """测试 schema v1.0 转换为 CaptureData"""
    
    # 模拟 analyze 输出
    schema_v1_data = {
        'schema_version': '1.0',
        'meta': {'capture_file': 'test.rdc'},
        'resources': {
            'textures': {
                'tex_001': {'name': 'Albedo', 'width': 1024, 'height': 1024, 'format': 'BC7'},
                'tex_002': {'name': 'Normal', 'width': 512, 'height': 512, 'format': 'BC5'},
            },
            'buffers': {
                'buf_001': {'name': 'VB0', 'size_bytes': 65536},
            }
        },
        'events': [{'id': 1, 'name': 'Draw'}],
        'summary': {'total_draw_calls': 100},
    }
    
    # 转换
    from rdc_analyzer.parsers.rdc_loader import _convert_schema_v1_to_capture_data
    result = _convert_schema_v1_to_capture_data(schema_v1_data)
    
    # 验证格式
    assert 'textures' in result
    assert isinstance(result['textures'], list)
    assert len(result['textures']) == 2
    
    assert 'buffers' in result
    assert isinstance(result['buffers'], list)
    assert len(result['buffers']) == 1
    
    assert 'statistics' in result
    assert result['statistics']['total_draw_calls'] == 100
    
    # 验证保留了源 schema 标记
    assert result.get('_source_schema') == '1.0'


def test_non_v1_schema_passthrough():
    """测试非 v1.0 数据原样返回"""
    
    legacy_data = {
        'textures': [{'id': 1, 'name': 'test'}],
        'buffers': [],
    }
    
    from rdc_analyzer.parsers.rdc_loader import _convert_schema_v1_to_capture_data
    result = _convert_schema_v1_to_capture_data(legacy_data)
    
    # 应该原样返回
    assert result == legacy_data
```

### 验证方式

```bash
cd scripts/rdc_analyzer

# 1. 运行新测试
py -3 -m pytest tests -v -k "schema" 

# 2. 运行 compare 相关测试
py -3 -m pytest tests -q -k "compare or loader"

# 3. 全量测试
py -3 -m pytest tests -q --ignore=tests/test_audit.py
```

### Git 提交模板

```bash
git add scripts/rdc_analyzer/parsers/rdc_loader.py
git add scripts/rdc_analyzer/tests/test_rdc_loader.py  # 或 test_schema_bridge.py
git commit -m "feat(rdc-analyzer): 添加 schema v1.0 → CaptureData 转换桥接 (P0-4)

- 新增 _convert_schema_v1_to_capture_data() 函数
- 检测 schema_version=1.0 并转换为 DiffEngine 期望格式
- resources dict → textures/buffers/shaders list
- summary → statistics 映射
- 新增 2 个测试用例

审计修复: P0-4 目标2 闭环"
```

---

## 📞 完成后通知

完成上述所有任务后，请：

1. 确保所有 checkbox 已勾选
2. 运行最终验证：
   ```bash
   cd scripts/rdc_analyzer
   py -3 -m pytest tests -q
   ```
3. 回复 Agent A："**修复 3+4 已完成，请验收**"，并附上：
   - 测试结果截图/输出
   - Git commit hash
   - 任何遇到的问题或偏离计划的说明

---

## ⚠️ 注意事项

1. **不要修改 `test_audit.py`** — 这是 Agent A 负责的
2. **保持向后兼容** — 旧格式数据应继续工作
3. **测试先行** — 修改前确保现有测试通过
4. **小步提交** — 修复 3 和修复 4 分开提交

---

## 📚 参考资源

- 审计报告: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md`
- 项目 README: `scripts/rdc_analyzer/README.md`
- 测试配置: `scripts/rdc_analyzer/pytest.ini`
