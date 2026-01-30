import os
import sys

TEST_DIR = os.path.dirname(__file__)
EXPORTERS_DIR = os.path.join(TEST_DIR, "..", "exporters")
sys.path.insert(0, os.path.abspath(EXPORTERS_DIR))

from unity_manifest import build_manifest


def test_manifest_contains_required_keys():
    manifest = build_manifest(event_id=5, api="d3d11", mesh={}, textures=[], shaders={})
    for key in ["eventId", "api", "mesh", "textures", "shaders"]:
        assert key in manifest
