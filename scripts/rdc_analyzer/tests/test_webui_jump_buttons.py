#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebUI jump button wiring tests.
"""

from pathlib import Path


def _read_template(name: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "templates" / name).read_text(encoding="utf-8")


def test_jump_button_wiring_and_api_signature():
    nav_js = _read_template("navigation.js")
    events_html = _read_template("events.html")
    textures_html = _read_template("textures.html")
    shaders_html = _read_template("shaders.html")

    assert "jumpToRenderDoc" in nav_js
    assert "/api/jump" in nav_js
    assert "target" in nav_js.lower()

    assert (
        "jumpToRenderDoc('event'" in events_html
        or 'jumpToRenderDoc("event"' in events_html
    )
    assert (
        "jumpToRenderDoc('texture'" in textures_html
        or 'jumpToRenderDoc("texture"' in textures_html
    )
    assert (
        "jumpToRenderDoc('shader'" in shaders_html
        or 'jumpToRenderDoc("shader"' in shaders_html
    )
