import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from converters.fbx_profiles import build_profile


def test_build_profile_unity():
    profile = build_profile("unity")
    assert profile["axis"] == "Y_UP"
    assert profile["unit"] == "METER"


def test_build_profile_unreal():
    profile = build_profile("unreal")
    assert profile["axis"] == "Z_UP"
    assert profile["unit"] == "CENTIMETER"
