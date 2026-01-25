#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adreno GPU 分析器
=================

提供 Adreno 启发式分析，以及可选的 Snapdragon Profiler CLI 集成入口。
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAnalyzer
from .performance_analyzer import is_compressed_format
from ..core.enums import Category, Severity
from ..core.types import Issue, TextureInfo, DrawCallInfo


@dataclass(frozen=True)
class AdrenoGPUInfo:
    name: str
    architecture: str
    tier: str
    year: int


ADRENO_GPU_LIST: List[AdrenoGPUInfo] = [
    AdrenoGPUInfo("Adreno 750", architecture="A7xx", tier="flagship", year=2023),
    AdrenoGPUInfo("Adreno 740", architecture="A7xx", tier="flagship", year=2022),
    AdrenoGPUInfo("Adreno 730", architecture="A7xx", tier="flagship", year=2021),
    AdrenoGPUInfo("Adreno 660", architecture="A6xx", tier="flagship", year=2020),
    AdrenoGPUInfo("Adreno 650", architecture="A6xx", tier="flagship", year=2019),
    AdrenoGPUInfo("Adreno 640", architecture="A6xx", tier="premium", year=2019),
    AdrenoGPUInfo("Adreno 630", architecture="A6xx", tier="flagship", year=2018),
    AdrenoGPUInfo("Adreno 620", architecture="A6xx", tier="mainstream", year=2020),
    AdrenoGPUInfo("Adreno 618", architecture="A6xx", tier="entry", year=2020),
    AdrenoGPUInfo("Adreno 612", architecture="A6xx", tier="entry", year=2019),
]


class AdrenoAnalyzer(BaseAnalyzer):
    """Adreno GPU 分析器"""

    name = "adreno"
    description = "Adreno analyzer - heuristic checks + optional profiler hook"
    dependencies = ["frame", "resource", "pass"]

    def analyze(self) -> List[Issue]:
        issues: List[Issue] = []
        mode = getattr(self.context, "adreno_mode", "heuristic")

        if mode in ("profiler", "auto"):
            profiler_issues = self._try_profiler()
            if profiler_issues:
                issues.extend(profiler_issues)
            if mode == "profiler":
                return issues

        issues.extend(self._check_gmem_bandwidth())
        issues.extend(self._check_texture_decompression())
        issues.extend(self._check_shader_alu_pressure())
        return issues

    def _try_profiler(self) -> List[Issue]:
        profiler_path = getattr(self.context, "adreno_profiler_path", None)
        if profiler_path and os.path.exists(profiler_path):
            return [
                Issue(
                    severity=Severity.INFO,
                    category=Category.MOBILE,
                    code="ADRENO_PROFILER",
                    message="Snapdragon Profiler CLI 已配置，但当前未启用详细解析流程。",
                )
            ]

        return [
            Issue(
                severity=Severity.INFO,
                category=Category.MOBILE,
                code="ADRENO_PROFILER",
                message="Snapdragon Profiler CLI 不可用，已降级为启发式分析。",
            )
        ]

    def _check_gmem_bandwidth(self) -> List[Issue]:
        rt_bytes = self._estimate_render_target_bytes()
        threshold = self.get_threshold("tile_rt_bytes", 64 * 1024 * 1024)
        if rt_bytes > threshold:
            return [
                Issue(
                    severity=Severity.WARNING,
                    category=Category.PERFORMANCE,
                    code="ADRENO_001",
                    message=(
                        f"GMEM 带宽压力：RT 总量 {rt_bytes / (1024 * 1024):.1f}MB "
                        f"(阈值 {threshold / (1024 * 1024):.1f}MB)"
                    ),
                    threshold=threshold,
                    actual=rt_bytes,
                )
            ]
        return []

    def _check_texture_decompression(self) -> List[Issue]:
        textures: List[TextureInfo] = self.context.textures or []
        threshold_kb = self.get_threshold("uncompressed_texture_threshold_kb", 256)
        large_uncompressed = [
            tex for tex in textures
            if not tex.is_render_target
            and not is_compressed_format(tex.format or "")
            and tex.memory_size >= threshold_kb * 1024
        ]

        if len(large_uncompressed) >= 5:
            return [
                Issue(
                    severity=Severity.INFO,
                    category=Category.MOBILE,
                    code="ADRENO_002",
                    message=(
                        f"检测到 {len(large_uncompressed)} 张大尺寸未压缩纹理，"
                        "可能引发解压缩开销"
                    ),
                    threshold=threshold_kb * 1024,
                    actual=len(large_uncompressed),
                )
            ]
        return []

    def _check_shader_alu_pressure(self) -> List[Issue]:
        draws: List[DrawCallInfo] = self.context.draw_calls or []
        if not draws:
            return []

        vertex_threshold = 100000
        high_alu_draws = [
            dc for dc in draws
            if (dc.vertex_count or 0) * max(dc.instance_count or 1, 1) >= vertex_threshold
        ]

        if high_alu_draws:
            return [
                Issue(
                    severity=Severity.INFO,
                    category=Category.PERFORMANCE,
                    code="ADRENO_003",
                    message=(
                        f"{len(high_alu_draws)} 个 Draw 估算 ALU 压力偏高 "
                        f"(阈值 {vertex_threshold} vertices)"
                    ),
                    threshold=vertex_threshold,
                    actual=len(high_alu_draws),
                )
            ]
        return []

    def _estimate_render_target_bytes(self) -> int:
        total = 0
        for tex in self.context.textures or []:
            if not tex.is_render_target:
                continue
            if tex.memory_size:
                total += tex.memory_size
                continue

            bpp = self._estimate_bpp(tex.format)
            total += tex.width * tex.height * bpp * max(tex.sample_count, 1)
        return total

    def _estimate_bpp(self, fmt: str) -> int:
        fmt_upper = (fmt or "").upper()
        if "R32G32B32A32" in fmt_upper:
            return 16
        if "R16G16B16A16" in fmt_upper:
            return 8
        if "R11G11B10" in fmt_upper:
            return 4
        if "R16G16" in fmt_upper:
            return 4
        if "R16" in fmt_upper:
            return 2
        if "R8G8B8A8" in fmt_upper or "B8G8R8A8" in fmt_upper:
            return 4
        if "R8G8" in fmt_upper:
            return 2
        if "R8" in fmt_upper:
            return 1
        if "D24" in fmt_upper or "D32" in fmt_upper:
            return 4
        return 4
