#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc shell script smoke tests.
"""


def test_renderdoc_shell_script_exports_run():
    import rdc_analyzer.tools.renderdoc_shell_analyze as mod

    assert hasattr(mod, "run")
