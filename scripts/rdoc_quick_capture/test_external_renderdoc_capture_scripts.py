import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
QUICK_CAPTURE_DIR = ROOT / "scripts" / "rdoc_quick_capture"


def _load_trigger_module():
    module_path = QUICK_CAPTURE_DIR / "trigger_target_capture.py"
    assert module_path.exists(), "trigger_target_capture.py should be formalized"
    spec = importlib.util.spec_from_file_location("trigger_target_capture", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeTarget(object):
    def __init__(self, messages):
        self.messages = list(messages)
        self.triggered_frames = []
        self.shutdown_called = False

    def TriggerCapture(self, num_frames):
        self.triggered_frames.append(num_frames)

    def ReceiveMessage(self, progress):
        assert progress is None
        if self.messages:
            return self.messages.pop(0)
        return SimpleNamespace(type="Noop")

    def GetAPI(self):
        return "D3D11"

    def GetPID(self):
        return 4242

    def Shutdown(self):
        self.shutdown_called = True


class _FakeRenderDoc(object):
    class TargetControlMessageType:
        Noop = "Noop"
        NewCapture = "NewCapture"

    def __init__(self, target):
        self.target = target
        self.create_calls = []

    def CreateTargetControl(self, url, ident, client_name, force_connection):
        self.create_calls.append((url, ident, client_name, force_connection))
        return self.target


def test_trigger_capture_reports_new_capture_details():
    trigger = _load_trigger_module()
    new_capture = SimpleNamespace(
        path=r"F:\Code\S1\LocalData\RenderDocCaptures\codex_external.rdc",
        frameNumber=37,
        api="D3D11",
    )
    target = _FakeTarget(
        [
            SimpleNamespace(type=_FakeRenderDoc.TargetControlMessageType.Noop),
            SimpleNamespace(type=_FakeRenderDoc.TargetControlMessageType.NewCapture, newCapture=new_capture),
        ]
    )
    fake_rd = _FakeRenderDoc(target)

    result = trigger.trigger_capture(
        renderdoc_module=fake_rd,
        target_control_port=38920,
        timeout_sec=1.0,
        poll_interval_sec=0.0,
    )

    assert fake_rd.create_calls == [("localhost", 38920, "codex_target_capture.py", True)]
    assert target.triggered_frames == [1]
    assert target.shutdown_called is True
    assert result == {
        "path": str(Path(new_capture.path)),
        "frame": 37,
        "api": "D3D11",
        "pid": 4242,
    }


def test_trigger_capture_times_out_and_closes_target():
    trigger = _load_trigger_module()
    target = _FakeTarget([SimpleNamespace(type=_FakeRenderDoc.TargetControlMessageType.Noop)])
    fake_rd = _FakeRenderDoc(target)

    try:
        trigger.trigger_capture(
            renderdoc_module=fake_rd,
            target_control_port=38920,
            timeout_sec=0.0,
            poll_interval_sec=0.0,
        )
    except TimeoutError as exc:
        assert "NewCapture" in str(exc)
    else:
        raise AssertionError("Expected timeout waiting for NewCapture")

    assert target.triggered_frames == [1]
    assert target.shutdown_called is True


def test_external_capture_powershell_contract():
    script_path = QUICK_CAPTURE_DIR / "capture_s1_external_renderdoc.ps1"
    assert script_path.exists(), "capture_s1_external_renderdoc.ps1 should exist"
    text = script_path.read_text(encoding="utf-8")
    lower = text.lower()

    assert "--opt-capture-all-cmd-lists" in text
    assert "--enable-renderdoc" in text
    assert "--disable-streamline" in text
    assert "--suppress=RenderDoc" in text
    assert "D:\\Code\\git\\renderdoc\\x64\\Development\\renderdoc.dll" in text
    assert "C:\\Program Files\\RenderDoc\\renderdoc.dll" in text
    assert "one_click_bundle_report.py" in text
    assert "D:\\Program Files\\Python36\\python.exe" in text
    assert "PreCaptureDelaySec" in text
    assert "--force-texture-export" in text
    assert "--smoke-viewports" in text
    assert "1366x768,1920x1080" in text
    assert "38920..38927" in text
    assert "ui_smoke_result.json" in text
    assert "overall_pass" in text
    assert "Plugins.xml" not in text
    assert "reg add" not in lower
    assert "renderdoccmd inject" not in lower
