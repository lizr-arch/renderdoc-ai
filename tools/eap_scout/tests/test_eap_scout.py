import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import eap_scout


class EAPScoutTests(unittest.TestCase):
    def write_file(self, root: Path, rel: str, text: str) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_empty_repo_classifies_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "empty"
            repo.mkdir()

            result = eap_scout.scan_repo(repo, max_files=100)

            self.assertEqual(result["repo"]["type"], "unknown")
            self.assertEqual(result["recommendation"]["recommended_next_task"], "RepoReconOnly")

    def test_renderdoc_fork_fixture_classifies_renderdoc_fork(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "renderdoc"
            self.write_file(repo, "renderdoc/api/app/renderdoc_app.h", "RENDERDOC_GetAPI\n")
            self.write_file(repo, "renderdoc/replay/app_api.cpp", "SetObjectAnnotation\n")
            self.write_file(repo, "qrenderdoc/qrenderdoc.pro", "TEMPLATE = app\n")
            self.write_file(repo, "renderdoccmd/renderdoccmd.cpp", "int main() { return 0; }\n")

            result = eap_scout.scan_repo(repo, max_files=100)

            self.assertEqual(result["repo"]["type"], "renderdoc_fork")
            self.assertTrue(result["recommendation"]["is_wrong_repo_for_engine_emission"])
            self.assertEqual(result["recommendation"]["recommended_next_task"], "RepoReconOnly")

    def test_fake_engine_fixture_finds_render_graph_rhi_and_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "engine"
            self.write_file(
                repo,
                "Source/Runtime/Renderer/RenderGraph.cpp",
                "class RenderGraph { void AddPass(); void ExecutePass(); };\n",
            )
            self.write_file(
                repo,
                "Source/Runtime/RHI/RHICommandList.h",
                "class RHICommandList { void DrawIndexed(); void Dispatch(); };\n",
            )
            self.write_file(
                repo,
                "Source/Runtime/Renderer/GpuMarker.cpp",
                "void BeginGpuMarker(const char* Name); void EndGpuMarker();\n",
            )

            result = eap_scout.scan_repo(repo, max_files=100)

            self.assertEqual(result["repo"]["type"], "game_engine_repo")
            self.assertEqual(result["concepts"]["render_graph"]["status"], "found")
            self.assertEqual(result["concepts"]["rhi"]["status"], "found")
            self.assertEqual(result["concepts"]["gpu_marker"]["status"], "found")
            self.assertEqual(result["recommendation"]["recommended_next_task"], "RenderDocBridge MVP")

    def test_scan_writes_manifest_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "engine"
            out = Path(tmp) / "out"
            self.write_file(repo, "Source/Renderer/RHI.cpp", "RHICommandList DrawIndexed Dispatch\n")

            manifest = eap_scout.run_scan(repo, out, engine="auto", max_files=100)

            self.assertTrue((out / "eap_repo_manifest.json").exists())
            self.assertTrue((out / "EAP_IMPLEMENTATION_MAP.md").exists())
            self.assertTrue((out / "EAP_HOOK_CANDIDATES.md").exists())
            self.assertTrue((out / "codex_next_prompt.md").exists())
            self.assertTrue((out / "evidence" / "repo_inventory.json").exists())
            self.assertEqual(manifest["schema_version"], "eap_scout_manifest.v1")

    def test_prompt_command_writes_prompt_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "renderdoc"
            out = Path(tmp) / "scan"
            prompt = Path(tmp) / "next_prompt.md"
            self.write_file(repo, "renderdoc/api/app/renderdoc_app.h", "RENDERDOC_GetAPI\n")
            self.write_file(repo, "renderdoc/replay/app_api.cpp", "SetCommandAnnotation\n")
            self.write_file(repo, "qrenderdoc/qrenderdoc.pro", "TEMPLATE = app\n")
            self.write_file(repo, "renderdoccmd/renderdoccmd.cpp", "int main() { return 0; }\n")
            eap_scout.run_scan(repo, out, engine="auto", max_files=100)

            eap_scout.run_prompt(out / "eap_repo_manifest.json", "renderdoc_bridge", prompt)

            text = prompt.read_text(encoding="utf-8")
            self.assertIn("do not implement engine-side bridge", text.lower())
            self.assertIn("RenderDoc fork", text)

    def test_large_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "large"
            self.write_file(repo, "Source/Renderer.cpp", "RHICommandList\n")
            large = repo / "Source/Huge.cpp"
            large.parent.mkdir(parents=True, exist_ok=True)
            large.write_bytes(b"a" * (2 * 1024 * 1024 + 1))

            result = eap_scout.scan_repo(repo, max_files=100)

            self.assertGreater(result["scan"]["skip_reasons"].get("too_large", 0), 0)
            self.assertEqual(result["concepts"]["rhi"]["status"], "found")

    def test_third_party_directory_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "skip"
            self.write_file(repo, "ThirdParty/Renderer/RHI.cpp", "RHICommandList RenderGraph BeginGpuMarker\n")
            self.write_file(repo, "Source/Game.cpp", "int main() { return 0; }\n")

            result = eap_scout.scan_repo(repo, max_files=100)

            self.assertGreater(result["scan"]["skip_reasons"].get("ignored_dir:ThirdParty", 0), 0)
            self.assertEqual(result["concepts"]["rhi"]["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
