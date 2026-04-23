from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List


class SnapshotTemplateRenderer:
    """Renders minimal offline HTML pages from snapshot.v1 payload only."""

    PAGE_ORDER = ("index", "events", "textures", "shaders", "pipelines")

    def __init__(self, output_dir: str | Path, capture_name: str = ""):
        self.output_dir = Path(output_dir)
        self.capture_name = capture_name
        self._page_status: Dict[str, str] = {}

    def render(self, snapshot: Dict[str, Any]) -> Dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        snapshot_version = snapshot.get("schema_version", "snapshot.v1")
        generated_at = (
            snapshot.get("meta", {}).get("generated_at")
            or datetime.now().astimezone().isoformat()
        )
        source = snapshot.get("meta", {}).get("source", "offline")
        capture_name = (
            snapshot.get("meta", {}).get("capture_name")
            or self.capture_name
            or "RenderDoc Capture"
        )
        self._page_status = self._build_page_status(snapshot)

        pages = {
            "index": self._render_index(snapshot, capture_name),
            "events": self._render_events(snapshot, capture_name),
            "textures": self._render_textures(snapshot, capture_name),
            "shaders": self._render_shaders(snapshot, capture_name),
            "pipelines": self._render_pipelines(snapshot, capture_name),
        }

        outputs: Dict[str, str] = {}
        for page_name, html in pages.items():
            page_path = self.output_dir / f"{page_name}.html"
            page_path.write_text(html, encoding="utf-8")
            outputs[page_name] = str(page_path)

        manifest = {
            "schema_version": "template.v1",
            "snapshot_version": snapshot_version,
            "source": source,
            "generated_at": generated_at,
            "pages": list(self.PAGE_ORDER),
            "page_files": {name: f"{name}.html" for name in self.PAGE_ORDER},
            "capture_name": capture_name,
        }
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        outputs["manifest"] = str(manifest_path)

        self._write_common_css()
        return outputs

    def _render_index(self, snapshot: Dict[str, Any], capture_name: str) -> str:
        overview = snapshot.get("overview", {}) or {}
        summary = overview.get("summary", {}) or {}
        findings = snapshot.get("findings", []) or []
        recommendations = snapshot.get("recommendations", []) or []
        availability = snapshot.get("availability", {}) or {}
        preflight = snapshot.get("preflight", {}) or {}

        summary_items = [
            ("Actions", summary.get("actions", 0)),
            ("Draw Calls", summary.get("draw_calls", 0)),
            ("Dispatch Calls", summary.get("dispatch_calls", 0)),
            ("Textures", summary.get("textures", 0)),
            ("Shaders", summary.get("shaders", 0)),
        ]

        summary_html = "".join(
            f"<li><strong>{escape(label)}:</strong> {escape(str(value))}</li>"
            for label, value in summary_items
        )
        findings_html = (
            "".join(
                f"<li>{escape(item.get('title', item.get('description', 'finding')))}</li>"
                for item in findings
            )
            if findings
            else "<li>No findings generated in offline mode.</li>"
        )
        rec_html = (
            "".join(
                f"<li>{escape(item.get('title', 'recommendation'))}</li>"
                for item in recommendations
            )
            if recommendations
            else "<li>No recommendations.</li>"
        )
        availability_html = self._json_block(availability)
        preflight_html = self._json_block(preflight)

        body = f"""
<h1>{escape(capture_name)} - Offline Snapshot Report</h1>
{self._nav("index")}
<section>
  <h2>Overview</h2>
  <ul>{summary_html}</ul>
</section>
<section>
  <h2>Preflight</h2>
  {preflight_html}
</section>
<section>
  <h2>Findings</h2>
  <ul>{findings_html}</ul>
</section>
<section>
  <h2>Recommendations</h2>
  <ul>{rec_html}</ul>
  <p><a href="pipelines.html">Open pipelines page</a></p>
</section>
<section>
  <h2>Availability</h2>
  {availability_html}
</section>
"""
        return self._wrap_html("Index", body)

    def _render_events(self, snapshot: Dict[str, Any], capture_name: str) -> str:
        actions = snapshot.get("actions", []) or []
        items: List[str] = []
        for action in actions:
            event_id = str(action.get("event_id", "0"))
            name = action.get("name", "Unknown")
            action_type = action.get("type", "Draw")
            marker = action.get("marker", "")
            indices = action.get("indices", 0)
            vertices = action.get("vertices", 0)
            instances = action.get("instances", 1)
            items.append(
                f"""
<article id="event-{escape(event_id)}" class="card">
  <h3>Event {escape(event_id)}: {escape(name)}</h3>
  <p><strong>Type:</strong> {escape(str(action_type))}</p>
  <p><strong>Vertices:</strong> {escape(str(vertices))} | <strong>Indices:</strong> {escape(str(indices))} | <strong>Instances:</strong> {escape(str(instances))}</p>
  <p><strong>Marker:</strong> {escape(str(marker) or "-")}</p>
</article>
"""
            )
        events_html = "".join(items) if items else "<p>No actions available.</p>"
        body = f"""
<h1>{escape(capture_name)} - Events</h1>
{self._nav("events")}
{events_html}
"""
        return self._wrap_html("Events", body)

    def _render_textures(self, snapshot: Dict[str, Any], capture_name: str) -> str:
        textures = snapshot.get("resources", {}).get("textures", []) or []
        cards: List[str] = []
        for tex in textures:
            resource_id = str(tex.get("resource_id", ""))
            name = tex.get("name", "")
            width = tex.get("width", 0)
            height = tex.get("height", 0)
            fmt = tex.get("format", "Unknown")
            size_bytes = tex.get("size_bytes", 0)
            thumbnail = tex.get("thumbnail", "")
            if thumbnail:
                preview = f'<img src="{escape(str(thumbnail))}" alt="thumbnail for {escape(name)}" class="thumbnail"/>'
            else:
                preview = '<div class="thumbnail placeholder">No thumbnail</div>'
            cards.append(
                f"""
<article id="resource-{escape(resource_id)}" class="card">
  <h3>{escape(name)} <span class="muted">({escape(resource_id)})</span></h3>
  {preview}
  <p><strong>Size:</strong> {escape(str(width))}x{escape(str(height))}</p>
  <p><strong>Format:</strong> {escape(str(fmt))}</p>
  <p><strong>Bytes:</strong> {escape(str(size_bytes))}</p>
</article>
"""
            )
        textures_html = "".join(cards) if cards else "<p>No texture resources available.</p>"
        body = f"""
<h1>{escape(capture_name)} - Textures</h1>
{self._nav("textures")}
{textures_html}
"""
        return self._wrap_html("Textures", body)

    def _render_shaders(self, snapshot: Dict[str, Any], capture_name: str) -> str:
        shaders = snapshot.get("shaders", []) or []
        cards: List[str] = []
        for shader in shaders:
            shader_id = str(shader.get("shader_id", shader.get("id", "")))
            name = shader.get("name", "")
            stage = shader.get("stage", "Unknown")
            source_code = shader.get("source_code", "") or "// source unavailable in offline mode"
            cards.append(
                f"""
<article id="shader-{escape(shader_id)}" class="card">
  <h3>{escape(name)} <span class="muted">({escape(shader_id)})</span></h3>
  <p><strong>Stage:</strong> {escape(str(stage))}</p>
  <pre>{escape(source_code)}</pre>
</article>
"""
            )
        shaders_html = "".join(cards) if cards else "<p>No shaders available.</p>"
        body = f"""
<h1>{escape(capture_name)} - Shaders</h1>
{self._nav("shaders")}
{shaders_html}
"""
        return self._wrap_html("Shaders", body)

    def _render_pipelines(self, snapshot: Dict[str, Any], capture_name: str) -> str:
        pipelines = snapshot.get("pipelines", []) or []
        recommendations = snapshot.get("recommendations", []) or []
        availability = snapshot.get("availability", {}) or {}
        preflight = snapshot.get("preflight", {}) or {}
        items: List[str] = []
        for rec in recommendations:
            title = rec.get("title", "Recommendation")
            description = rec.get("description", "")
            suggestion = rec.get("suggestion", "")
            severity = rec.get("severity", "info")
            items.append(
                f"""
<article class="card">
  <h3>{escape(title)}</h3>
  <p><strong>Severity:</strong> {escape(str(severity))}</p>
  <p>{escape(description)}</p>
  <p><strong>Suggestion:</strong> {escape(suggestion)}</p>
</article>
"""
            )
        recommendations_html = "".join(items) if items else "<p>No recommendations.</p>"

        if pipelines:
            pipelines_html = "".join(self._render_pipeline_card(pipeline) for pipeline in pipelines)
        else:
            missing_fields = availability.get("missing_fields", []) or []
            missing_fields_html = (
                "".join(f"<li>{escape(str(field))}</li>" for field in missing_fields)
                if missing_fields
                else "<li>No missing pipeline fields reported.</li>"
            )
            mcp_hint = availability.get("mcp_hint", "")
            mcp_hint_html = (
                f"<p><strong>MCP Hint:</strong> {escape(str(mcp_hint))}</p>" if mcp_hint else ""
            )
            pipelines_html = f"""
<article class="card">
  <h2>Pipeline summary unavailable</h2>
  <p>No pipeline summaries were captured in this snapshot. The page is still emitted to keep bundle navigation stable.</p>
  {mcp_hint_html}
  <h3>Missing fields</h3>
  <ul>{missing_fields_html}</ul>
</article>
"""

        body = f"""
<h1>{escape(capture_name)} - Pipelines</h1>
{self._nav("pipelines")}
<section>
  <h2>Pipeline Summary</h2>
  {pipelines_html}
</section>
<section>
  <h2>Preflight</h2>
  {self._json_block(preflight)}
</section>
<section>
  <h2>Availability</h2>
  {self._json_block(availability)}
</section>
<section>
  <h2>Recommendations</h2>
  {recommendations_html}
</section>
"""
        return self._wrap_html("Pipelines", body)

    def _write_common_css(self) -> None:
        css_path = self.output_dir / "common.css"
        css_path.write_text(
            """body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f8fa;color:#1c1d20}
h1{margin:0 0 12px 0}
nav{display:flex;gap:10px;margin:0 0 18px 0}
nav a{color:#0a58ca;text-decoration:none;font-weight:600}
section{margin-bottom:20px}
.card{background:#fff;border:1px solid #d8dde6;border-radius:8px;padding:14px;margin:10px 0}
.muted{color:#666}
pre{background:#0e1116;color:#d6deeb;padding:12px;border-radius:6px;overflow:auto}
.thumbnail{max-width:280px;max-height:180px;display:block;border:1px solid #ddd;background:#fff}
.thumbnail.placeholder{display:flex;align-items:center;justify-content:center;width:280px;height:120px;color:#666;background:#f2f3f5}
.json-block{background:#fff;border:1px solid #d8dde6;border-radius:8px;padding:10px;white-space:pre-wrap}
""",
            encoding="utf-8",
        )

    def _nav(self, active: str) -> str:
        links = []
        for page in self.PAGE_ORDER:
            label = self._format_nav_label(page, self._page_status.get(page, "available"))
            if page == active:
                links.append(f"<strong>{escape(label)}</strong>")
            else:
                links.append(f'<a href="{page}.html">{escape(label)}</a>')
        return f"<nav>{' | '.join(links)}</nav>"

    def _build_page_status(self, snapshot: Dict[str, Any]) -> Dict[str, str]:
        availability = snapshot.get("availability", {}) or {}
        fields = availability.get("fields", {}) or {}
        textures = snapshot.get("resources", {}).get("textures", []) or []
        actions = snapshot.get("actions", []) or []
        shaders = snapshot.get("shaders", []) or []
        pipelines = snapshot.get("pipelines", []) or []
        return {
            "index": self._normalize_page_status(availability.get("status"), "available"),
            "events": self._normalize_page_status(
                fields.get("actions"), "available" if actions else "unavailable"
            ),
            "textures": self._normalize_page_status(
                fields.get("resources"), "available" if textures else "unavailable"
            ),
            "shaders": self._normalize_page_status(
                fields.get("shaders"), "available" if shaders else "unavailable"
            ),
            "pipelines": self._normalize_page_status(
                fields.get("pipelines"), "available" if pipelines else "unavailable"
            ),
        }

    @staticmethod
    def _normalize_page_status(status: Any, fallback: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized in ("available", "ok"):
            return "available"
        if normalized in ("partial", "warning"):
            return "partial"
        if normalized in ("missing", "unavailable", "error"):
            return "unavailable"
        return fallback

    @staticmethod
    def _format_nav_label(page: str, status: str) -> str:
        label = "Pipelines" if page == "pipelines" else page.capitalize()
        if status == "partial":
            return f"{label} (Partial)"
        if status == "unavailable":
            return f"{label} (Unavailable)"
        return label

    def _render_pipeline_card(self, pipeline: Dict[str, Any]) -> str:
        pipeline_id = str(pipeline.get("pipeline_id", "pipeline"))
        event_id = str(pipeline.get("event_id", ""))
        graphics_api = pipeline.get("graphics_api", "Unknown")
        evidence_items: List[str] = []

        vs_ref = pipeline.get("vs_ref") or {}
        if vs_ref:
            evidence_items.append(
                f"<li><strong>VS:</strong> {self._render_ref_link(vs_ref, 'shaders', 'shader', 'shader')}</li>"
            )

        ps_ref = pipeline.get("ps_ref") or {}
        if ps_ref:
            evidence_items.append(
                f"<li><strong>PS:</strong> {self._render_ref_link(ps_ref, 'shaders', 'shader', 'shader')}</li>"
            )

        render_targets = pipeline.get("render_target_refs", []) or []
        if render_targets:
            targets = ", ".join(
                self._render_ref_link(target, "textures", "resource", "texture")
                for target in render_targets
            )
            evidence_items.append(f"<li><strong>Render Targets:</strong> {targets}</li>")

        depth_target = pipeline.get("depth_target_ref") or {}
        if depth_target:
            evidence_items.append(
                f"<li><strong>Depth:</strong> {self._render_ref_link(depth_target, 'textures', 'resource', 'depth target')}</li>"
            )

        if not evidence_items:
            evidence_items.append("<li>No linked shader or resource evidence.</li>")

        details: List[str] = []
        for label, key in (
            ("Blend", "blend"),
            ("Depth / Stencil", "depth_stencil"),
            ("Rasterizer", "rasterizer"),
            ("Vertex Layout", "vertex_layout"),
        ):
            payload = pipeline.get(key)
            if payload:
                details.append(f"<section><h3>{escape(label)}</h3>{self._json_block(payload)}</section>")

        details_html = "".join(details) if details else "<p>No pipeline state details available.</p>"
        event_html = (
            f'<a href="events.html#event-{escape(event_id)}">Event {escape(event_id)}</a>'
            if event_id
            else "No event link"
        )

        return f"""
<article id="pipeline-{escape(pipeline_id)}" class="card">
  <h3>Pipeline {escape(pipeline_id)}</h3>
  <p><strong>Event:</strong> {event_html}</p>
  <p><strong>Graphics API:</strong> {escape(str(graphics_api))}</p>
  <ul>{''.join(evidence_items)}</ul>
  {details_html}
  <section>
    <h3>Availability</h3>
    {self._json_block(pipeline.get("availability", {}))}
  </section>
</article>
"""

    @staticmethod
    def _render_ref_link(ref: Dict[str, Any], page: str, anchor_prefix: str, fallback: str) -> str:
        ref_id = str(ref.get("shader_id") or ref.get("resource_id") or ref.get("id") or "")
        label = str(ref.get("label") or ref.get("name") or ref_id or fallback)
        if ref_id:
            return f'<a href="{page}.html#{anchor_prefix}-{escape(ref_id)}">{escape(label)}</a>'
        return escape(label)

    def _json_block(self, payload: Dict[str, Any]) -> str:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        return f'<pre class="json-block">{escape(text)}</pre>'

    @staticmethod
    def _wrap_html(title: str, body: str) -> str:
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            f"  <title>{escape(title)}</title>\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
            "  <link rel=\"stylesheet\" href=\"common.css\" />\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )
