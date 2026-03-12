import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Union

from rdc_analyzer.bridge.analysis_to_bundle import analysis_to_bundle
from rdc_analyzer.report_bundle_generator import ReportBundleGenerator


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_issue_record(issue: Dict[str, Any]) -> Dict[str, Any]:
    severity = issue.get("severity") or issue.get("level") or issue.get("priority") or "info"
    message = issue.get("message") or issue.get("title") or issue.get("detail") or ""
    code = issue.get("code") or issue.get("rule_id") or issue.get("id")
    category = issue.get("category") or issue.get("type")
    suggestion = issue.get("suggestion") or issue.get("action") or issue.get("fix")

    event_ids = _coerce_list(issue.get("event_ids") or issue.get("eventIds"))
    event_id = issue.get("event_id") or issue.get("eventId") or issue.get("eid")
    if event_id is not None and event_id not in event_ids:
        event_ids.append(event_id)

    resource_ids = _coerce_list(issue.get("resource_ids") or issue.get("resourceIds"))
    resource_id = issue.get("resource_id") or issue.get("resourceId")
    if resource_id and resource_id not in resource_ids:
        resource_ids.append(resource_id)

    record: Dict[str, Any] = {
        "severity": severity,
        "message": message,
    }
    if code:
        record["code"] = code
    if category:
        record["category"] = category
    if event_ids:
        record["event_ids"] = event_ids
        record["event_id"] = event_ids[0]
    if resource_ids:
        record["resource_ids"] = resource_ids
        record["resource_id"] = resource_ids[0]
    if suggestion:
        record["suggestion"] = suggestion
    evidence = issue.get("evidence")
    if isinstance(evidence, dict) and evidence:
        record["evidence"] = evidence
    return record


def _export_issues(analysis: Dict[str, Any], output_dir: Path) -> None:
    issues = analysis.get("issues", [])
    rows: List[Dict[str, Any]] = []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                rows.append(_normalize_issue_record(issue))

    json_path = output_dir / "issues_export.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")

    csv_path = output_dir / "issues_export.csv"
    fieldnames = [
        "severity",
        "message",
        "code",
        "category",
        "event_id",
        "event_ids",
        "resource_id",
        "resource_ids",
        "suggestion",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "severity": row.get("severity", ""),
                    "message": row.get("message", ""),
                    "code": row.get("code", ""),
                    "category": row.get("category", ""),
                    "event_id": row.get("event_id", ""),
                    "event_ids": ";".join(str(v) for v in row.get("event_ids", [])),
                    "resource_id": row.get("resource_id", ""),
                    "resource_ids": ";".join(str(v) for v in row.get("resource_ids", [])),
                    "suggestion": row.get("suggestion", ""),
                }
            )


def generate_report_from_analysis(
    analysis_path: Union[str, Path],
    output_dir: Union[str, Path],
    capture_name: str,
) -> None:
    analysis_path = Path(analysis_path)
    output_dir = Path(output_dir)
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    bundle = analysis_to_bundle(data)

    generator = ReportBundleGenerator(output_dir, capture_name)
    generator.set_events(bundle.events)
    generator.set_textures(bundle.textures)
    generator.set_shaders(bundle.shaders, mali_data=None, usage_map=bundle.shader_usage)
    generator.stats.update(bundle.stats)
    generator.set_performance_data(data)
    generator.generate_all()
    _export_issues(data, output_dir)
