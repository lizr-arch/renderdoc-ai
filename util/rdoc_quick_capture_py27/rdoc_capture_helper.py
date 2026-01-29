# -*- coding: utf-8 -*-
"""
Small helper for in-game Python console usage (Python 2.7).
Requires rdoc_capture.pyd to be importable.
"""

import rdoc_capture


def init(dll_path=None, capture_path=None, title=None):
    """
    Initialize RenderDoc API and optional capture settings.
    Returns True if RenderDoc API is available.
    """
    if dll_path:
        rdoc_capture.load(dll_path)
    else:
        rdoc_capture.load()

    if capture_path:
        rdoc_capture.set_capture_path(capture_path)

    if title:
        rdoc_capture.set_capture_title(title)

    return rdoc_capture.is_available()


def trigger(title=None):
    """
    Trigger a single capture. Optionally override title for this capture.
    """
    if title:
        rdoc_capture.set_capture_title(title)
    rdoc_capture.trigger_capture()
