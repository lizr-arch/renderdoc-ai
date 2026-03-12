# Standards Traceability & WHAT/WHY/HOW Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-24
**Owner:** Agent01
**Last Updated:** 2026-01-24
**Plan File:** `plans/2026-01-24-165506-Agent01-StandardsTraceability.md`

**Goal:** 为所有规则补齐“WHAT/WHY/HOW + 标准可追溯”元数据闭环，并在 RULES.md 中自动生成与可验证。

**Architecture:** 规则元数据由 BaseRule 的可选字段与生成器的默认推导共同提供；阈值标准来源集中登记在 thresholds.py 并由生成器关联到规则的阈值键；测试确保规则输出元数据与标准来源全覆盖且非空。

**Tech Stack:** Python 3, pytest, rdc_analyzer rules/config, Markdown generation.

**Success Criteria (measurable):**
- RULES.md 中每条规则都输出 WHAT/WHY/HOW，且非空。
- 每个规则用到的阈值键都能在标准来源映射中找到来源说明。
- 自动化测试覆盖：元数据非空、标准来源覆盖、文档行数 < 800。

**Acceptance Criteria:**
- 生成器输出包含 WHAT/WHY/HOW 与标准来源字段。
- 缺失元数据或来源将触发测试失败。
- 生成文档不超过 800 行，便于阅读维护。

**Verification Commands:**
- `cd scripts/rdc_analyzer && py -3 -m pytest -q -rs`    Expected: `all tests passed`（允许已知 skipped）
- `py -3 -c "import sys; sys.path.insert(0, "D:/Code/git/renderdoc/scripts"); import rdc_analyzer.scripts.generate_rules_doc as g; sys.argv=["generate_rules_doc.py","--write"]; raise SystemExit(g.main())"`    Expected: `RULES.md` 更新且 < 800 行

**Evidence:**
- `scripts/rdc_analyzer/RULES.md`
- pytest 输出日志

**Estimation:**
- Effort: 0.5-1 day
- Story Points: 3
- Original Estimate: 1 day

**Risk Register (impact/likelihood/mitigation):**
- 中/中：规则数量多导致元数据质量不一致 → 允许默认推导 + 关键规则手工补强。
- 中/低：阈值键遗漏来源 → 单测强制覆盖并阻止合并。
- 低/中：文档超过 800 行 → 生成器行数检查 + 简化描述。

## Game Dev: Memory & Resource Budget (Leak Checks)
- 文档生成不引入运行时内存风险；仅在离线生成时写文件，避免持久驻留数据结构。

## Game Dev: Asset Pipeline
- 标准来源和规则元数据统一在代码内维护，确保资产/规则“来源路径单一”。

## Game Dev: Crash Repro + Dumps/Symbols
- 变更为纯 Python 逻辑与文档生成，不改变 RenderDoc 回放路径；无需新增 crash 复现步骤。

---

## Scope
- In: 规则元数据闭环、标准来源映射、生成器扩展、测试与文档更新。
- Out: 规则逻辑行为变更、阈值数值调整、外部数据抓取。

## Assumptions
- 规则的 WHAT/WHY/HOW 允许默认推导，但可被规则显式覆盖。
- 标准来源当前以“内部基线/经验”形式记录，后续可补充外部文档链接。

## Repo / File List (line refs)
- `scripts/rdc_analyzer/rules/base.py:15-90`（BaseRule 元数据字段）
- `scripts/rdc_analyzer/config/thresholds.py:64-232`（阈值 + 来源映射）
- `scripts/rdc_analyzer/scripts/generate_rules_doc.py:84-210`（生成器输出扩展）
- `scripts/rdc_analyzer/tests/test_rules_doc_generator.py:1-80`（生成器测试扩展）
- `scripts/rdc_analyzer/tests/test_threshold_sources.py:1-80`（阈值来源覆盖测试）
- `scripts/rdc_analyzer/RULES.md`（再生成）

## Approach (Pseudo-code)
```python
# 1) BaseRule: 新增可选元数据字段
class BaseRule(ABC):
    what: str = ""
    why: str = ""
    how: str = ""

# 2) thresholds.py: 标准来源映射
THRESHOLD_SOURCES = {
  "max_draw_calls": {
     "source": "Internal baseline (2025-01)",
     "rationale": "Drawcall budget for 60fps",
     "last_reviewed": "2026-01-24",
  },
  ...
}

def get_threshold_sources():
    return _apply_threshold_aliases(THRESHOLD_SOURCES)

# 3) generator: 优先使用规则字段，缺失时推导
what = rule_cls.what or f"{rule["name"]}"
why = rule_cls.why or CATEGORY_DEFAULT_WHY[rule["category"]]
how = rule_cls.how or build_how_from_thresholds(threshold_keys)

# 4) 输出 WHAT/WHY/HOW + 标准来源
```

## Impact Analysis
- 正面：规则文档与标准来源可追溯，符合你的闭环要求。
- 负面：需要新增并维护阈值来源映射，后期需持续更新。

---

## Task Checklist（TDD, 2-5 分钟粒度）

### P2-1 BaseRule 元数据字段 + 单测
- [x] 写失败测试：规则元数据输出 WHAT/WHY/HOW 均非空  
  **测试代码（完整片段）**：
  ```python
  # scripts/rdc_analyzer/tests/test_rules_metadata.py
  from rdc_analyzer.rules import RuleRegistry, register_all_rules
  from rdc_analyzer.scripts.generate_rules_doc import collect_rules

  def test_rules_have_non_empty_metadata():
      register_all_rules()
      rules = collect_rules()
      for rule in rules:
          assert rule.get("what"), f"{rule["rule_id"]} missing WHAT"
          assert rule.get("why"), f"{rule["rule_id"]} missing WHY"
          assert rule.get("how"), f"{rule["rule_id"]} missing HOW"
  ```
- [x] 运行失败测试：`py -3 -m pytest -q -rs tests/test_rules_metadata.py`
- [x] 最小实现：BaseRule 增加 what/why/how 字段 + 生成器默认推导  
  **代码片段（完整替换示例）**：
  ```python
  # scripts/rdc_analyzer/rules/base.py
  class BaseRule(ABC):
      ...
      # 元数据（可选覆盖）
      what: str = ""
      why: str = ""
      how: str = ""
  ```
- [x] 运行测试：`py -3 -m pytest -q -rs tests/test_rules_metadata.py`
- [x] 提交：`feat(rdc-analyzer): add rule metadata defaults`

### P2-2 阈值标准来源映射
- [x] 写失败测试：所有规则用到的阈值键必须有来源  
  **测试代码（完整片段）**：
  ```python
  # scripts/rdc_analyzer/tests/test_threshold_sources.py
  from rdc_analyzer.config import get_threshold_sources
  from rdc_analyzer.scripts.generate_rules_doc import collect_rules

  def test_threshold_sources_cover_rule_keys():
      sources = get_threshold_sources()
      rules = collect_rules()
      for rule in rules:
          for th in rule.get("thresholds", []):
              key = th["key"]
              assert key in sources, f"missing source for {key}"
  ```
- [x] 运行失败测试：`py -3 -m pytest -q -rs tests/test_threshold_sources.py`
- [x] 最小实现：新增 THRESHOLD_SOURCES + get_threshold_sources  
  **代码片段（完整示例）**：
  ```python
  # scripts/rdc_analyzer/config/thresholds.py
  THRESHOLD_SOURCES: Dict[str, Dict[str, str]] = {
      "max_draw_calls": {
          "source": "Internal baseline (2025-01)",
          "rationale": "Drawcall budget for 60fps",
          "last_reviewed": "2026-01-24",
      },
      "large_texture_threshold_mb": {
          "source": "Internal baseline (2025-01)",
          "rationale": "VRAM cap for 2K targets",
          "last_reviewed": "2026-01-24",
      },
  }

  def get_threshold_sources() -> Dict[str, Dict[str, str]]:
      return _apply_threshold_aliases(THRESHOLD_SOURCES.copy())
  ```
- [x] 运行测试：`py -3 -m pytest -q -rs tests/test_threshold_sources.py`
- [x] 提交：`feat(rdc-analyzer): add threshold source registry`

### P2-3 生成器输出 WHAT/WHY/HOW + 标准来源
- [x] 写失败测试：输出包含 WHAT/WHY/HOW 与来源字段  
  **测试代码（完整片段）**：
  ```python
  # scripts/rdc_analyzer/tests/test_rules_doc_generator.py (append)
  from rdc_analyzer.scripts.generate_rules_doc import render_markdown, collect_rules

  def test_rules_doc_includes_metadata_and_sources():
      content = render_markdown(collect_rules())
      assert "**WHAT**" in content
      assert "**WHY**" in content
      assert "**HOW**" in content
      assert "**标准来源**" in content
  ```
- [x] 运行失败测试：`py -3 -m pytest -q -rs tests/test_rules_doc_generator.py`
- [x] 最小实现：生成器补充字段并使用来源映射  
  **代码片段（完整示例）**：
  ```python
  # scripts/rdc_analyzer/scripts/generate_rules_doc.py
  from rdc_analyzer.config import get_thresholds, get_threshold_sources

  CATEGORY_DEFAULT_WHY = {
      "performance": "避免渲染性能退化",
      "memory": "控制资源内存增长",
      "state": "减少状态切换开销",
  }

  def _build_how(thresholds):
      if not thresholds:
          return "规则内部固定条件"
      keys = [t["key"] for t in thresholds]
      return "检查阈值是否超标: " + ", ".join(keys)

  # render_markdown
  lines.append(f"- **WHAT**: {rule["what"]}")
  lines.append(f"- **WHY**: {rule["why"]}")
  lines.append(f"- **HOW**: {rule["how"]}")
  lines.append("- **标准来源**:")
  for th in rule["thresholds"]:
      src = sources.get(th["key"], {})
      lines.append(f"  - {th["key"]}: {src.get("source", "")}")
  ```
- [x] 运行测试：`py -3 -m pytest -q -rs tests/test_rules_doc_generator.py`
- [x] 提交：`docs(rdc-analyzer): render rule metadata and sources`

### P2-4 生成 RULES.md + 行数验证
- [x] 运行生成：`py -3 -c "import sys; sys.path.insert(0, "D:/Code/git/renderdoc/scripts"); import rdc_analyzer.scripts.generate_rules_doc as g; sys.argv=["generate_rules_doc.py","--write"]; raise SystemExit(g.main())"`
- [x] 校验行数 < 800
- [x] 提交：`docs(rdc-analyzer): regenerate RULES.md with metadata`

---

**Approval:** WAIT for user confirmation before entering /do.
