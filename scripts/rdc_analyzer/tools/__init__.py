# Tools for rdc_analyzer automation.

# NOTE: Do not import install_ui_extension eagerly. The RenderDoc embedded Python
# is 3.6 and will hit SyntaxError if it evaluates `from __future__ import annotations`
# inside install_ui_extension. Import it explicitly when needed.
__all__ = ["install_ui_extension"]
