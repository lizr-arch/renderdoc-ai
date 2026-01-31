from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


DOC_ROOT = Path("docs/analysis/codex_rdc_analyzer")
TOOL_DOC_ROOT = Path("scripts/rdc_analyzer/docs")
AI_INDEX = Path("scripts/rdc_analyzer/.ai/INDEX.md")


READING_ORDER_DOC_INDEX = [
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md", "阅读总览"),
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md", "A/B/C 路线"),
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md", "Schema/Bridge"),
    ("docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md", "数据丰富度基线"),
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md", "验证流程"),
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md", "优先级/计划"),
    ("docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_BUILD.md", "环境/编译"),
]

READING_ORDER_WORK_SUMMARY = [
    ("WORK_SUMMARY_ARCH.md", "架构/模块/文件结构"),
    ("WORK_SUMMARY_ROUTES.md", "A/B/C 路线 + 数据来源 + 验证状态"),
    ("WORK_SUMMARY_SCHEMA.md", "Schema / Pipeline / Bridge"),
    ("2026-01-31-rdc-analyzer-data-richness-baseline.md", "数据丰富度基线"),
    ("WORK_SUMMARY_VERIFICATION.md", "证据化验证 + CLI 用法"),
    ("WORK_SUMMARY_ROADMAP.md", "未来优先级 + 决策 + 参考"),
    ("WORK_SUMMARY_BUILD.md", "环境/编译"),
]


@dataclass
class DocMeta:
    path: Path
    title: str
    summary: str
    keywords: str
    routes: str


def load_text(path: Path) -> Tuple[str, str]:
    data = path.read_bytes()
    enc = "utf-8"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("gb18030")
        enc = "gb18030"
    if enc == "utf-8" and "\ufffd" in text:
        try:
            text_gb = data.decode("gb18030")
            if text_gb.count("\ufffd") < text.count("\ufffd"):
                text = text_gb
                enc = "gb18030"
        except Exception:
            pass
    return text, enc


def save_text(path: Path, text: str, enc: str) -> None:
    path.write_text(text, encoding=enc)


def _extract_value(lines: List[str], markers: List[str]) -> str:
    for line in lines:
        for marker in markers:
            if marker in line:
                tail = line.split(marker, 1)[-1].strip()
                if tail:
                    return tail
    return ""


def extract_meta(path: Path) -> DocMeta:
    text, _ = load_text(path)
    lines = [l.strip() for l in text.splitlines()]
    title = path.stem
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    summary = _extract_value(lines, ["WHAT:", "WHAT：", "- WHAT:", "- WHAT："])
    if not summary:
        summary = "未标注（原因：源文档无 WHAT 段）"

    keywords = _extract_value(lines, ["关键词：", "关键词:", "关键字：", "关键字:"])
    if not keywords:
        keywords = "未标注（原因：源文档无关键词段）"

    routes = _extract_value(lines, ["适用路线：", "适用路线:", "适用路线"])
    if not routes:
        routes = "未标注（原因：源文档无适用路线段）"

    return DocMeta(path=path, title=title, summary=summary, keywords=keywords, routes=routes)


def _replace_section(text: str, header: str, new_lines: List[str]) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        return text
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[: start + 1] + [""] + new_lines + [""] + lines[end:])


def update_doc_index() -> None:
    path = DOC_ROOT / "DOC_INDEX.md"
    text, enc = load_text(path)

    # Reading order
    reading_lines = [
        f"{i + 1}. `{doc}`（{label}）" for i, (doc, label) in enumerate(READING_ORDER_DOC_INDEX)
    ]
    text = _replace_section(text, "## 阅读顺序（建议）", reading_lines)

    # Append missing entries
    existing = set()
    for line in text.splitlines():
        if "路径：" in line and "`" in line:
            part = line.split("`", 1)[-1]
            existing.add(part.split("`", 1)[0])

    docs = []
    for doc in sorted(DOC_ROOT.glob("*.md")):
        if doc.name == "DOC_INDEX.md":
            continue
        docs.append(extract_meta(doc))

    for meta in docs:
        path_str = str(meta.path).replace("\\", "/")
        if path_str in existing:
            continue
        text += (
            f"\n### {meta.path.stem}（{meta.title}）\n"
            f"- 简介：{meta.summary}\n"
            f"- 关键词：{meta.keywords}\n"
            f"- 适用路线：{meta.routes}\n"
            f"- 路径：`{path_str}`\n"
        )

    save_text(path, text, enc)


def update_work_summary() -> None:
    path = DOC_ROOT / "WORK_SUMMARY_2025-01-21.md"
    text, enc = load_text(path)

    reading_lines = [
        f"{i + 1}. `{doc}` （{label}）" for i, (doc, label) in enumerate(READING_ORDER_WORK_SUMMARY)
    ]
    text = _replace_section(text, "## 推荐阅读顺序", reading_lines)

    doc_list_lines = [f"- `{doc}`" for doc, _ in READING_ORDER_WORK_SUMMARY]
    text = _replace_section(text, "## 文档清单", doc_list_lines)

    save_text(path, text, enc)


def update_tool_docs_index() -> None:
    path = TOOL_DOC_ROOT / "INDEX.md"
    text, enc = load_text(path)

    docs = [d for d in sorted(TOOL_DOC_ROOT.glob("*.md")) if d.name != "INDEX.md"]
    entries = []
    for doc in docs:
        meta = extract_meta(doc)
        entries.append(
            f"| [{doc.name}]({doc.name}) | {meta.summary} | {meta.keywords} |"
        )

    section_header = "## 自动同步（未归类）"
    table_lines = [
        "## 自动同步（未归类）",
        "",
        "| 文档 | 说明 | 关键词 |",
        "|------|------|--------|",
    ] + entries

    if section_header in text:
        text = _replace_section(text, section_header, table_lines[2:])
    else:
        text += "\n\n" + "\n".join(table_lines)

    save_text(path, text, enc)


def update_ai_index() -> None:
    if not AI_INDEX.exists():
        return
    text, enc = load_text(AI_INDEX)
    section_header = "## 外部文档索引（自动同步）"
    lines = [
        section_header,
        "",
        "- [DOC_INDEX.md](../../docs/analysis/codex_rdc_analyzer/DOC_INDEX.md)（总索引入口）",
        "- [数据丰富度基线](../../docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md)",
    ]
    if section_header in text:
        text = _replace_section(text, section_header, lines[2:])
    else:
        text += "\n\n" + "\n".join(lines)
    save_text(AI_INDEX, text, enc)


def main() -> None:
    update_doc_index()
    update_work_summary()
    update_tool_docs_index()
    update_ai_index()
    print("sync_doc_indexes: done")


if __name__ == "__main__":
    main()
