# RenderDoc in-process capture helper (DX11)
# Intended to run inside the game process via Python.
# Uses RenderDoc App API (RENDERDOC_GetAPI) via ctypes.

import ctypes
import os

# RENDERDOC_Version values (see renderdoc_app.h)
RENDERDOC_API_VERSION_1_6_0 = 10600
RENDERDOC_API_VERSION_1_5_0 = 10500
RENDERDOC_API_VERSION_1_4_2 = 10402

# Function pointer helpers (cdecl on Windows)
CFN_void = ctypes.CFUNCTYPE(None)
CFN_void_ccharp = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

RENDERDOC_API_BASE_FIELDS = [
    ("GetAPIVersion", ctypes.c_void_p),
    ("SetCaptureOptionU32", ctypes.c_void_p),
    ("SetCaptureOptionF32", ctypes.c_void_p),
    ("GetCaptureOptionU32", ctypes.c_void_p),
    ("GetCaptureOptionF32", ctypes.c_void_p),
    ("SetFocusToggleKeys", ctypes.c_void_p),
    ("SetCaptureKeys", ctypes.c_void_p),
    ("GetOverlayBits", ctypes.c_void_p),
    ("MaskOverlayBits", ctypes.c_void_p),
    ("RemoveHooks", ctypes.c_void_p),
    ("UnloadCrashHandler", ctypes.c_void_p),
    ("SetCaptureFilePathTemplate", ctypes.c_void_p),
    ("GetCaptureFilePathTemplate", ctypes.c_void_p),
    ("GetNumCaptures", ctypes.c_void_p),
    ("GetCapture", ctypes.c_void_p),
    ("TriggerCapture", ctypes.c_void_p),
]

RENDERDOC_API_1_6_0_FIELDS = RENDERDOC_API_BASE_FIELDS + [
    ("IsTargetControlConnected", ctypes.c_void_p),
    ("LaunchReplayUI", ctypes.c_void_p),
    ("SetActiveWindow", ctypes.c_void_p),
    ("StartFrameCapture", ctypes.c_void_p),
    ("IsFrameCapturing", ctypes.c_void_p),
    ("EndFrameCapture", ctypes.c_void_p),
    ("TriggerMultiFrameCapture", ctypes.c_void_p),
    ("SetCaptureFileComments", ctypes.c_void_p),
    ("DiscardFrameCapture", ctypes.c_void_p),
    ("ShowReplayUI", ctypes.c_void_p),
    ("SetCaptureTitle", ctypes.c_void_p),
]


class RENDERDOC_API_BASE(ctypes.Structure):
    _fields_ = RENDERDOC_API_BASE_FIELDS


class RENDERDOC_API_1_6_0(ctypes.Structure):
    _fields_ = RENDERDOC_API_1_6_0_FIELDS


class RenderDocInProcess(object):
    def __init__(self, dll_path=None):
        self._api = None
        self._api_ext = None

        if dll_path and os.path.exists(dll_path):
            rdoc = ctypes.CDLL(dll_path)
        else:
            rdoc = ctypes.CDLL("renderdoc.dll")

        getapi = rdoc.RENDERDOC_GetAPI
        getapi.restype = ctypes.c_int
        getapi.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

        api_ptr = ctypes.c_void_p()
        ok = getapi(RENDERDOC_API_VERSION_1_6_0, ctypes.byref(api_ptr))
        if ok and api_ptr.value:
            self._api_ext = ctypes.cast(api_ptr, ctypes.POINTER(RENDERDOC_API_1_6_0)).contents
            self._api = self._api_ext
        else:
            for version in (RENDERDOC_API_VERSION_1_5_0, RENDERDOC_API_VERSION_1_4_2):
                ok = getapi(version, ctypes.byref(api_ptr))
                if ok and api_ptr.value:
                    self._api = ctypes.cast(api_ptr, ctypes.POINTER(RENDERDOC_API_BASE)).contents
                    break

    def is_available(self):
        return self._api is not None

    def set_capture_path(self, path):
        if not self._api or not path:
            return
        fn = CFN_void_ccharp(self._api.SetCaptureFilePathTemplate)
        fn(path.encode("utf-8"))

    def set_capture_title(self, title):
        if not self._api_ext or not title:
            return
        fn = CFN_void_ccharp(self._api_ext.SetCaptureTitle)
        fn(title.encode("utf-8"))

    def trigger_capture(self):
        if not self._api:
            return
        fn = CFN_void(self._api.TriggerCapture)
        fn()


# Example usage inside game Python update:
# rdoc = RenderDocInProcess(r"F:\Code\S1\RenderDoc\renderdoc.dll")
# if rdoc.is_available() and in_target_ui:
#     rdoc.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
#     rdoc.set_capture_title("UI_Target")
#     rdoc.trigger_capture()
