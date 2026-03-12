#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tile-Based GPU 分析器
=====================

基于启发式估算 Tile 相关指标，并写入 AnalysisContext 供规则使用。
"""

from typing import Dict, Any, List

from .base import BaseAnalyzer
from ..core.tile_memory import get_tile_memory_config, estimate_tile_memory


class TileBasedAnalyzer(BaseAnalyzer):
    """Tile-Based 架构分析器"""

    name = "tile_based"
    description = "Tile-based analyzer - estimates tile metrics"
    dependencies = ["frame", "resource", "pass"]

    def analyze(self) -> None:
        draws = self.context.parsed.draws or []

        # 确保 pass 信息可用
        if not self.context.passes:
            try:
                from .pass_analyzer import PassAnalyzer
                PassAnalyzer(self.context).analyze()
            except Exception:
                pass

        passes = self.context.passes or []

        if not draws and not passes:
            self.context.tile_metrics = {}
            return

        viewport_w = self.context.frame_summary.viewport_width or 0
        viewport_h = self.context.frame_summary.viewport_height or 0
        if (viewport_w == 0 or viewport_h == 0) and passes:
            viewport_w = max((p.viewport_width for p in passes), default=0)
            viewport_h = max((p.viewport_height for p in passes), default=0)

        if viewport_w == 0 or viewport_h == 0:
            viewport_w, viewport_h = 100, 100
            viewport_estimated = True
        else:
            viewport_estimated = False

        base_pixels = max(viewport_w * viewport_h, 1)

        total_pixels = 0.0
        max_color_attachments = 0
        depth_enabled = False
        max_samples = 1
        rt_bytes_total = 0

        for draw in draws:
            state = draw.get("state", {}) or {}
            blend_enabled = (
                state.get("blend_enabled")
                or state.get("blendEnabled")
                or draw.get("blend_enabled")
                or draw.get("blendEnabled")
            )
            coverage = 1.0 if blend_enabled else 0.3
            total_pixels += base_pixels * coverage

            rts = draw.get("render_targets") or draw.get("renderTargets") or draw.get("rt_ids") or []
            if isinstance(rts, (list, tuple)):
                max_color_attachments = max(max_color_attachments, len(rts))

            depth_enabled = depth_enabled or bool(
                draw.get("depth_target")
                or draw.get("ds_id")
                or draw.get("depth_enabled")
            )

            sample_count = draw.get("sample_count") or draw.get("samples") or 1
            max_samples = max(max_samples, int(sample_count))

            if draw.get("rt_bytes"):
                rt_bytes_total += int(draw.get("rt_bytes") or 0)

        for pass_info in passes:
            if pass_info.color_attachments:
                max_color_attachments = max(max_color_attachments, len(pass_info.color_attachments))
            if pass_info.depth_attachment:
                depth_enabled = True
            max_samples = max(max_samples, int(pass_info.sample_count or 1))

        if max_color_attachments == 0:
            max_color_attachments = 1

        bytes_per_pixel = 4
        if rt_bytes_total == 0:
            rt_bytes_total = base_pixels * bytes_per_pixel * max_color_attachments * max_samples

        config = get_tile_memory_config(getattr(self.context, "tile_gpu", "Generic-Tile"))
        tile_estimate = estimate_tile_memory(
            config=config,
            color_attachments=max_color_attachments,
            depth_enabled=depth_enabled,
            bytes_per_pixel=bytes_per_pixel,
            sample_count=max_samples,
            estimated=True,
            reason="heuristic",
        )

        overdraw_ratio = (total_pixels / base_pixels) if draws else 1.0
        load_store_bytes = int(rt_bytes_total * 2)

        # Load/Store / MSAA / Transient / Marker 统计
        load_ops = 0
        store_ops = 0
        load_store_passes = 0
        load_store_attachment_count = 0
        load_store_available = False

        msaa_passes = 0
        msaa_no_resolve_passes = 0
        msaa_check_available = False

        transient_checked_passes = 0
        transient_missing_passes = 0
        transient_check_available = False

        marker_checked_passes = 0
        marker_missing_passes = 0

        for pass_info in passes:
            attachments = []
            if pass_info.color_attachments:
                attachments.extend(pass_info.color_attachments)
            if pass_info.depth_attachment:
                attachments.append(pass_info.depth_attachment)

            if attachments:
                ops_in_pass = False
                for att in attachments:
                    load_op = (att.get("loadOp", "") or "").upper()
                    store_op = (att.get("storeOp", "") or "").upper()
                    if load_op or store_op:
                        ops_in_pass = True
                    if "LOAD" in load_op:
                        load_ops += 1
                    if "STORE" in store_op:
                        store_ops += 1
                if ops_in_pass:
                    load_store_available = True
                    load_store_passes += 1
                    load_store_attachment_count += len(attachments)

            if pass_info.sample_count > 1:
                msaa_check_available = True
                msaa_passes += 1
                if not pass_info.has_resolve:
                    msaa_no_resolve_passes += 1

            if pass_info.depth_attachment:
                transient_checked_passes += 1
                transient_check_available = True
                if not pass_info.has_transient_attachment:
                    transient_missing_passes += 1

            if pass_info.draw_count > 0:
                marker_checked_passes += 1
                if not pass_info.marker_name:
                    marker_missing_passes += 1

        metrics: Dict[str, Any] = {
            "overdraw_ratio": overdraw_ratio,
            "tile_memory_bytes": tile_estimate.estimated_bytes,
            "rt_bytes": rt_bytes_total,
            "load_store_bytes": load_store_bytes,
            "load_ops": load_ops,
            "store_ops": store_ops,
            "load_store_passes": load_store_passes,
            "load_store_attachment_count": load_store_attachment_count,
            "load_store_available": load_store_available,
            "msaa_samples": max_samples,
            "msaa_passes": msaa_passes,
            "msaa_no_resolve_passes": msaa_no_resolve_passes,
            "msaa_check_available": msaa_check_available,
            "transient_checked_passes": transient_checked_passes,
            "transient_missing_passes": transient_missing_passes,
            "transient_check_available": transient_check_available,
            "marker_checked_passes": marker_checked_passes,
            "marker_missing_passes": marker_missing_passes,
            "pass_switches": len(passes) if passes else 1,
            "tile_memory": tile_estimate.to_dict(),
            "viewport_width": viewport_w,
            "viewport_height": viewport_h,
            "estimated": True,
            "estimated_reason": "heuristic",
            "viewport_estimated": viewport_estimated,
        }

        self.context.tile_metrics = metrics
