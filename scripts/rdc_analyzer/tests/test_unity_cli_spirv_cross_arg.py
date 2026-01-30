import os
import sys

import pytest

TEST_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
sys.path.insert(0, SRC_DIR)

import export_unity_assets as cli


def test_cli_parses_spirv_cross_arg():
    args = cli.parse_args(
        [
            "--rdc",
            "cap.rdc",
            "--event",
            "1",
            "--api",
            "vulkan",
            "--out",
            "out",
            "--spirv-cross",
            "C:\\tools\\spirv-cross.exe",
        ]
    )
    assert args.spirv_cross == "C:\\tools\\spirv-cross.exe"


def test_vulkan_requires_spirv_cross():
    args = cli.parse_args(
        [
            "--rdc",
            "cap.rdc",
            "--event",
            "1",
            "--api",
            "vulkan",
            "--out",
            "out",
        ]
    )
    with pytest.raises(SystemExit):
        cli.validate_args(args)
