#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bundle 报告资源验证
===================

验证 textures.html / shaders.html 中关键渲染字段是否存在，
避免缩略图与源码被错误处理导致页面空白。
"""

import sys
from pathlib import Path

# 添加 scripts/rdc_analyzer 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_bundle_generator import ReportBundleGenerator  # noqa: E402


def test_texture_thumbnail_data_url(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
            "thumbnail": "AAAA",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "data:image/png;base64,AAAA" in html
