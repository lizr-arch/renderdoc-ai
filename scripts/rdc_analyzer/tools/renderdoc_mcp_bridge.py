#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Repo-local RenderDoc MCP file-IPC bridge.

This module is loaded inside qrenderdoc via --ui-python. It listens on the same
file protocol consumed by tools/mcp/mcp_server/bridge/client.py:
%TEMP%/renderdoc_mcp/request.json -> %TEMP%/renderdoc_mcp/response.json.

The bridge intentionally returns small mcp-query.v1 envelopes. It does not
generate report files or introduce a second report protocol.
"""

import base64
import json
import os
import tempfile
import threading
import time
import traceback
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


CONTRACT_VERSION = "mcp-query.v1"
DEFAULT_MAX_BYTES = 4096
HARD_MAX_BYTES = 65536


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _import_contract_helpers():
    tools_mcp = os.path.join(_repo_root(), "tools", "mcp")
    try:
        import sys

        if tools_mcp not in sys.path:
            sys.path.insert(0, tools_mcp)
        from snapshot_consumer import (  # type: ignore
            build_error_payload,
            build_mcp_envelope,
            normalize_mcp_success,
        )

        return build_mcp_envelope, build_error_payload, normalize_mcp_success
    except Exception:
        return _fallback_build_mcp_envelope, _fallback_build_error_payload, _fallback_normalize_mcp_success


def _fallback_build_mcp_envelope(
    *,
    ok: bool,
    data: Any,
    method: Optional[str],
    params: Dict[str, Any],
    availability: Optional[Dict[str, Any]] = None,
    evidence: Optional[List[Any]] = None,
    warnings: Optional[List[Any]] = None,
    recovery_hint: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
    source: str = "mcp",
) -> Dict[str, Any]:
    if availability is None:
        availability = {"status": "full", "missing_fields": [], "notes": []}
        if not ok:
            availability = {"status": "unavailable", "missing_fields": [], "notes": []}
    return {
        "ok": bool(ok),
        "contract_version": CONTRACT_VERSION,
        "data": data,
        "availability": _stable_object(availability),
        "evidence": _stable_object(evidence or []),
        "warnings": _stable_object(warnings or []),
        "recovery_hint": recovery_hint,
        "error": _stable_object(error) if error is not None else None,
        "method": method,
        "params": _stable_object(params or {}),
        "source": source,
    }


def _fallback_build_error_payload(
    *,
    code: str,
    message: str,
    method: Optional[str],
    params: Dict[str, Any],
    bridge_state: Optional[Dict[str, Any]] = None,
    capture_loaded: Optional[bool] = None,
) -> Dict[str, Any]:
    del bridge_state
    notes = []
    if capture_loaded is not None:
        notes.append("capture_loaded=%s" % bool(capture_loaded))
    return _fallback_build_mcp_envelope(
        ok=False,
        data=None,
        method=method,
        params=params,
        availability={"status": "unavailable", "missing_fields": [], "notes": notes},
        recovery_hint=_recovery_hint_for_error(code),
        error={"code": code, "message": message},
    )


def _fallback_normalize_mcp_success(result: Any, *, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(result, dict) and result.get("contract_version") == CONTRACT_VERSION and "ok" in result:
        payload = dict(result)
        payload.setdefault("data", None)
        payload.setdefault("availability", {"status": "full", "missing_fields": [], "notes": []})
        payload.setdefault("evidence", [])
        payload.setdefault("warnings", [])
        payload.setdefault("recovery_hint", None)
        payload.setdefault("error", None)
        payload["method"] = method
        payload["params"] = _stable_object(params)
        payload["source"] = "mcp"
        return payload
    return _fallback_build_mcp_envelope(ok=True, data=result, method=method, params=params)


_BUILD_MCP_ENVELOPE, _BUILD_ERROR_PAYLOAD, _NORMALIZE_MCP_SUCCESS = _import_contract_helpers()


class BridgeArgumentError(Exception):
    code = "invalid_argument"


class BridgeCaptureNotLoaded(Exception):
    code = "capture_not_loaded"


class BridgeNotFound(Exception):
    code = "not_found"


class BridgeUnsupported(Exception):
    code = "api_not_supported"


def _default_ipc_dir() -> str:
    return os.path.join(tempfile.gettempdir(), "renderdoc_mcp")


def _stable_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _stable_object(value[k]) for k in sorted(value.keys(), key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_stable_object(item) for item in value]
    return _jsonable(value)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, bytearray):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    try:
        return str(value)
    except Exception:
        return repr(value)


def _recovery_hint_for_error(code: str) -> str:
    if code == "capture_not_loaded":
        return "Open a capture in qrenderdoc and retry."
    if code == "invalid_argument":
        return "Check query params and retry."
    if code in ("not_found", "method_not_found"):
        return "Verify the method name or event/resource identifiers and retry."
    if code in ("api_not_supported", "unsupported_api"):
        return "Current RenderDoc API/driver path does not expose this field; keep the result partial."
    if code == "timeout":
        return "Check RenderDoc GUI responsiveness and retry get_capture_status."
    return "Inspect qrenderdoc logs and retry the query."


def _call(obj: Any, name: str, *args: Any) -> Any:
    fn = getattr(obj, name, None)
    if callable(fn):
        return fn(*args)
    raise AttributeError(name)


def _call_first(obj: Any, names: Iterable[str], *args: Any) -> Any:
    last_error = None
    for name in names:
        try:
            return _call(obj, name, *args)
        except Exception as ex:
            last_error = ex
    if last_error is not None:
        raise last_error
    raise AttributeError("no method names supplied")


def _attr(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if obj is None:
            return default
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            value = getattr(obj, name)
            if callable(value):
                try:
                    return value()
                except TypeError:
                    return value
            return value
    return default


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except Exception:
        return default


def _positive_int_param(params: Dict[str, Any], key: str, default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
    value = _as_int(params.get(key), default)
    if value is None:
        raise BridgeArgumentError("%s must be an integer" % key)
    if value < minimum:
        raise BridgeArgumentError("%s must be >= %d" % (key, minimum))
    if maximum is not None and value > maximum:
        return maximum
    return value


def _required_str_param(params: Dict[str, Any], key: str) -> str:
    value = str(params.get(key, "")).strip()
    if not value:
        raise BridgeArgumentError("%s is required" % key)
    return value


def _resource_id(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("ResourceId::"):
        return text.split("::", 1)[1]
    return text


def _format_name(fmt: Any) -> str:
    if fmt is None:
        return ""
    name_fn = getattr(fmt, "Name", None)
    if callable(name_fn):
        try:
            return str(name_fn())
        except Exception:
            pass
    return str(fmt)


def _bytes_from_result(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    try:
        return bytes(value)
    except Exception:
        if isinstance(value, str):
            return value.encode("utf-8")
    raise BridgeUnsupported("query returned non-byte data")


def _flags_list(flags: Any) -> List[str]:
    if flags is None:
        return []
    if isinstance(flags, (list, tuple)):
        return [str(item) for item in flags if str(item)]
    text = str(flags)
    if not text:
        return []
    parts = [part.strip() for part in text.replace("|", ",").split(",")]
    return [part for part in parts if part]


def _kind_from_action(action: Any) -> str:
    flags = " ".join(_flags_list(_attr(action, ("flags",), ""))).lower()
    name = str(_attr(action, ("name", "customName"), "")).lower()
    if "dispatch" in flags or name.startswith("dispatch"):
        return "dispatch"
    if "draw" in flags or "draw" in name:
        return "draw"
    if "clear" in flags or name.startswith("clear"):
        return "clear"
    if "marker" in flags:
        return "marker"
    children = _attr(action, ("children",), [])
    if children:
        return "marker"
    return "action"


class RenderDocMCPBridge:
    def __init__(self, context: Any, ipc_dir: Optional[str] = None, poll_interval: float = 0.05) -> None:
        self.context = context
        self.ipc_dir = ipc_dir or _default_ipc_dir()
        self.request_file = os.path.join(self.ipc_dir, "request.json")
        self.response_file = os.path.join(self.ipc_dir, "response.json")
        self.lock_file = os.path.join(self.ipc_dir, "lock")
        self.poll_interval = float(poll_interval)
        self._stop = threading.Event()
        self._thread = None

    def dispatch(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        if not isinstance(params, dict):
            params = {}
        if method not in self._methods():
            return self._error("method_not_found", "Unknown MCP method: %s" % method, method, params)
        try:
            if method not in ("get_capture_status", "list_captures", "open_capture") and not self._capture_loaded():
                raise BridgeCaptureNotLoaded("No active capture")
            return self._methods()[method](params)
        except (BridgeArgumentError, BridgeCaptureNotLoaded, BridgeNotFound, BridgeUnsupported) as ex:
            code = getattr(ex, "code", "internal_error")
            return self._error(code, str(ex), method, params)
        except Exception as ex:
            return self._error(
                "internal_error",
                "%s: %s\n%s" % (type(ex).__name__, ex, traceback.format_exc(limit=5)),
                method,
                params,
            )

    def process_next_request(self) -> bool:
        if not os.path.isdir(self.ipc_dir):
            os.makedirs(self.ipc_dir)
        if os.path.exists(self.lock_file) or not os.path.exists(self.request_file):
            return False

        try:
            with open(self.request_file, "r", encoding="utf-8") as handle:
                request = json.load(handle)
        except Exception as ex:
            response = {
                "id": None,
                "result": self._error("invalid_argument", "Invalid request JSON: %s" % ex, None, {}),
            }
            self._write_response(response)
            self._safe_remove(self.request_file)
            return True

        request_id = request.get("id")
        method = str(request.get("method", "")).strip()
        params = request.get("params") or {}
        if not isinstance(params, dict):
            result = self._error("invalid_argument", "params must be a JSON object", method or None, {})
        else:
            result = self.dispatch(method, params)
        self._write_response({"id": request_id, "result": result})
        self._safe_remove(self.request_file)
        return True

    def serve_forever(self) -> None:
        if not os.path.isdir(self.ipc_dir):
            os.makedirs(self.ipc_dir)
        while not self._stop.is_set():
            self.process_next_request()
            time.sleep(self.poll_interval)

    def start(self) -> "RenderDocMCPBridge":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self.serve_forever, name="RenderDocMCPBridge")
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _methods(self) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
        return {
            "get_capture_status": self._get_capture_status,
            "list_captures": self._list_captures,
            "open_capture": self._open_capture,
            "get_draw_calls": self._get_draw_calls,
            "get_frame_summary": self._get_frame_summary,
            "get_draw_call_details": self._get_draw_call_details,
            "get_action_timings": self._get_action_timings,
            "find_draws_by_shader": self._find_draws_by_shader,
            "find_draws_by_texture": self._find_draws_by_texture,
            "find_draws_by_resource": self._find_draws_by_resource,
            "get_pipeline_state": self._get_pipeline_state,
            "get_shader_info": self._get_shader_info,
            "get_texture_info": self._get_texture_info,
            "get_texture_data": self._get_texture_data,
            "get_buffer_contents": self._get_buffer_contents,
        }

    def _success(
        self,
        method: str,
        params: Dict[str, Any],
        data: Any,
        availability: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Any]] = None,
        warnings: Optional[List[Any]] = None,
        recovery_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = _BUILD_MCP_ENVELOPE(
            ok=True,
            data=data,
            method=method,
            params=params,
            availability=availability,
            evidence=evidence,
            warnings=warnings,
            recovery_hint=recovery_hint,
        )
        return _NORMALIZE_MCP_SUCCESS(payload, method=method, params=params)

    def _error(self, code: str, message: str, method: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        return _BUILD_ERROR_PAYLOAD(
            code=code,
            message=message,
            method=method,
            params=params,
            capture_loaded=self._capture_loaded(),
        )

    def _capture_loaded(self) -> bool:
        try:
            return bool(_call(self.context, "IsCaptureLoaded"))
        except Exception:
            return bool(_attr(self.context, ("loaded", "capture_loaded"), False))

    def _controller_call(self, func: Callable[[Any], Any]) -> Any:
        controller = _attr(self.context, ("controller", "replay_controller"), None)
        if controller is not None:
            return func(controller)

        replay = None
        try:
            replay = _call(self.context, "Replay")
        except Exception:
            pass
        if replay is not None:
            block_invoke = getattr(replay, "BlockInvoke", None)
            if callable(block_invoke):
                box: Dict[str, Any] = {}

                def callback(ctrl: Any) -> None:
                    box["value"] = func(ctrl)

                try:
                    block_invoke(callback)
                    return box.get("value")
                except TypeError:
                    block_invoke("RenderDocMCPBridge", callback)
                    return box.get("value")
            return func(replay)

        return func(self.context)

    def _root_actions(self) -> List[Any]:
        def getter(controller: Any) -> Any:
            return _call_first(controller, ("GetRootActions", "CurRootActions"))

        try:
            actions = self._controller_call(getter)
        except Exception:
            actions = _call_first(self.context, ("CurRootActions", "GetRootActions"))
        return list(actions or [])

    def _textures(self) -> List[Any]:
        try:
            return list(self._controller_call(lambda controller: _call(controller, "GetTextures")) or [])
        except Exception:
            try:
                return list(_call(self.context, "GetTextures") or [])
            except Exception:
                return []

    def _buffers(self) -> List[Any]:
        try:
            return list(self._controller_call(lambda controller: _call(controller, "GetBuffers")) or [])
        except Exception:
            try:
                return list(_call(self.context, "GetBuffers") or [])
            except Exception:
                return []

    def _set_event_and_pipeline(self, event_id: int) -> Any:
        def setter(controller: Any) -> Any:
            set_frame = getattr(controller, "SetFrameEvent", None)
            if callable(set_frame):
                set_frame(event_id, True)
            return _call_first(controller, ("GetPipelineState", "CurPipelineState"))

        try:
            return self._controller_call(setter)
        except Exception:
            set_event = getattr(self.context, "SetFrameEvent", None)
            if callable(set_event):
                set_event(event_id, True)
            else:
                set_event_id = getattr(self.context, "SetEventID", None)
                if callable(set_event_id):
                    try:
                        set_event_id([], event_id, event_id, True)
                    except Exception:
                        pass
            return _call(self.context, "CurPipelineState")

    def _action_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        def walk(actions: Iterable[Any], marker_path: List[str]) -> None:
            for action in actions or []:
                name = self._action_name(action)
                kind = _kind_from_action(action)
                event_id = _as_int(_attr(action, ("eventId", "event_id"), None), 0) or 0
                children = list(_attr(action, ("children",), []) or [])
                next_marker_path = list(marker_path)
                if kind == "marker" and name:
                    next_marker_path.append(name)
                else:
                    rows.append(
                        {
                            "event_id": event_id,
                            "name": name,
                            "flags": _flags_list(_attr(action, ("flags",), "")),
                            "kind": kind,
                            "marker_path": list(marker_path),
                            "draw_index_count": _as_int(_attr(action, ("numIndices", "num_indices"), None), 0) or 0,
                            "instance_count": _as_int(_attr(action, ("numInstances", "num_instances"), None), 0) or 0,
                            "dispatch_dimensions": self._dispatch_dimensions(action),
                            "shader_refs": self._shader_refs_from_action(action),
                            "resource_refs": self._resource_refs_from_action(action),
                            "_action": action,
                        }
                    )
                if children:
                    walk(children, next_marker_path)

        walk(self._root_actions(), [])
        rows.sort(key=lambda row: int(row.get("event_id") or 0))
        return rows

    def _action_name(self, action: Any) -> str:
        get_name = getattr(action, "GetName", None)
        if callable(get_name):
            try:
                structured_file = self._controller_call(lambda controller: _call(controller, "GetStructuredFile"))
                return str(get_name(structured_file))
            except Exception:
                try:
                    return str(get_name())
                except Exception:
                    pass
        return str(_attr(action, ("name", "customName", "custom_name"), ""))

    def _dispatch_dimensions(self, action: Any) -> Optional[Dict[str, int]]:
        x = _as_int(_attr(action, ("dispatchDimension", "dispatchDimensionX", "dispatch_x", "x"), None), None)
        y = _as_int(_attr(action, ("dispatchDimensionY", "dispatch_y", "y"), None), None)
        z = _as_int(_attr(action, ("dispatchDimensionZ", "dispatch_z", "z"), None), None)
        if x is None and y is None and z is None:
            return None
        return {"x": x or 0, "y": y or 0, "z": z or 0}

    def _shader_refs_from_action(self, action: Any) -> Dict[str, str]:
        refs = _attr(action, ("shader_refs", "shaderRefs", "shaders"), {}) or {}
        if isinstance(refs, dict):
            return {str(stage): _resource_id(ref) for stage, ref in refs.items() if _resource_id(ref)}
        return {}

    def _resource_refs_from_action(self, action: Any) -> List[str]:
        refs = _attr(action, ("resource_refs", "resourceRefs", "resources"), []) or []
        result = []
        if isinstance(refs, dict):
            refs = refs.values()
        for ref in refs:
            rid = _resource_id(ref)
            if rid:
                result.append(rid)
        return sorted(set(result))

    def _public_action_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(row)
        clean.pop("_action", None)
        if clean.get("dispatch_dimensions") is None:
            clean.pop("dispatch_dimensions", None)
        return _stable_object(clean)

    def _get_capture_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        loaded = self._capture_loaded()
        filename = ""
        if loaded:
            try:
                filename = str(_call(self.context, "GetCaptureFilename"))
            except Exception:
                filename = str(_attr(self.context, ("filename", "capture_filename"), ""))
        data = {
            "loaded": loaded,
            "filename": filename,
            "api": self._graphics_api(),
        }
        frame_number = self._frame_number()
        if frame_number is not None:
            data["frame_number"] = frame_number
        recovery_hint = None if loaded else "Open a capture in qrenderdoc and retry."
        return self._success("get_capture_status", params, data, recovery_hint=recovery_hint)

    def _graphics_api(self) -> str:
        for obj in (self.context, _attr(self.context, ("controller",), None)):
            if obj is None:
                continue
            try:
                api_props = _call(obj, "APIProps")
                api = _attr(api_props, ("pipelineType", "localRenderer", "driver"), "")
                if api:
                    return str(api)
            except Exception:
                pass
            try:
                api_props = _call(obj, "GetAPIProperties")
                api = _attr(api_props, ("pipelineType", "localRenderer", "driver"), "")
                if api:
                    return str(api)
            except Exception:
                pass
        return str(_attr(self.context, ("api", "graphics_api"), ""))

    def _frame_number(self) -> Optional[int]:
        try:
            frame = _call(self.context, "FrameInfo")
            return _as_int(_attr(frame, ("frameNumber", "frame_number"), None), None)
        except Exception:
            return _as_int(_attr(self.context, ("frame_number",), None), None)

    def _list_captures(self, params: Dict[str, Any]) -> Dict[str, Any]:
        status = self._get_capture_status({})["data"]
        items = []
        if status.get("loaded"):
            items.append(
                {
                    "filename": status.get("filename", ""),
                    "api": status.get("api", ""),
                    "frame_number": status.get("frame_number"),
                    "active": True,
                }
            )
        availability = {
            "status": "partial",
            "missing_fields": ["captures.multiple"],
            "notes": ["qrenderdoc UI context exposes the active capture; multi-capture enumeration is not exposed here."],
        }
        return self._success("list_captures", params, {"count": len(items), "items": items}, availability=availability)

    def _open_capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = _required_str_param(params, "path")
        if not os.path.isabs(path) or not path.lower().endswith(".rdc") or not os.path.exists(path):
            raise BridgeArgumentError("path must be an existing absolute .rdc path")
        availability = {
            "status": "partial",
            "missing_fields": ["capture.open"],
            "notes": ["Opening captures from ui-python is not executed by this bridge handler."],
        }
        data = {"requested_path": path, "opened": False}
        warnings = ["open_capture is advertised as partial to avoid unsafe asynchronous GUI load semantics."]
        return self._success(
            "open_capture",
            params,
            data,
            availability=availability,
            warnings=warnings,
            recovery_hint="Open the capture in qrenderdoc, then retry get_capture_status.",
        )

    def _get_draw_calls(self, params: Dict[str, Any]) -> Dict[str, Any]:
        max_count = _positive_int_param(params, "max_count", 200, minimum=1, maximum=1000)
        event_min = _as_int(params.get("event_min"), None)
        event_max = _as_int(params.get("event_max"), None)
        keyword = str(params.get("keyword", "")).strip().lower()
        rows = []
        for row in self._action_rows():
            event_id = int(row.get("event_id") or 0)
            if event_min is not None and event_id < event_min:
                continue
            if event_max is not None and event_id > event_max:
                continue
            if keyword and keyword not in str(row.get("name", "")).lower():
                continue
            rows.append(row)
        truncated = len(rows) > max_count
        items = [self._public_action_row(row) for row in rows[:max_count]]
        warnings = []
        if truncated:
            warnings.append("Result truncated to max_count=%d; narrow event range or keyword." % max_count)
        return self._success(
            "get_draw_calls",
            params,
            {"count": len(items), "total_matches": len(rows), "truncated": truncated, "items": items},
            warnings=warnings,
        )

    def _get_frame_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._action_rows()
        data = {
            "draw_call_count": sum(1 for row in rows if row.get("kind") == "draw"),
            "dispatch_count": sum(1 for row in rows if row.get("kind") == "dispatch"),
            "action_count": len(rows),
            "texture_count": len(self._textures()),
            "buffer_count": len(self._buffers()),
            "shader_count": len(self._collect_shader_refs(rows)),
        }
        return self._success("get_frame_summary", params, data)

    def _get_draw_call_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        event_id = _positive_int_param(params, "event_id", -1, minimum=1)
        row = self._find_action_row(event_id)
        missing = []
        warnings = []
        output_refs: List[str] = []
        depth_ref = None
        try:
            pipeline_payload, pipeline_missing = self._pipeline_payload(event_id)
            output_refs = pipeline_payload.get("render_target_refs") or []
            depth_ref = pipeline_payload.get("depth_target_ref")
            missing.extend(pipeline_missing)
        except Exception as ex:
            warnings.append("Pipeline details unavailable for event %d: %s" % (event_id, ex))
            missing.extend(["output_refs", "depth_ref"])
        data = {
            "event_id": event_id,
            "name": row.get("name", ""),
            "kind": row.get("kind", ""),
            "draw_index_count": row.get("draw_index_count", 0),
            "dispatch_dimensions": row.get("dispatch_dimensions"),
            "output_refs": output_refs,
            "depth_ref": depth_ref,
        }
        status = "partial" if missing else "full"
        availability = {"status": status, "missing_fields": sorted(set(missing)), "notes": []}
        return self._success("get_draw_call_details", params, data, availability=availability, warnings=warnings)

    def _get_action_timings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        max_count = _positive_int_param(params, "max_count", 200, minimum=1, maximum=1000)
        rows = self._action_rows()
        timings = []
        warnings = ["GPU action timing counters are not exposed by the repo-local ui-python bridge path."]
        data = {
            "available": False,
            "count": min(len(rows), max_count),
            "usable_count": 0,
            "zero_or_negative_count": 0,
            "total_gpu_ms": 0.0,
            "items": timings,
        }
        availability = {
            "status": "partial",
            "missing_fields": ["timings.items.duration_ms"],
            "notes": ["Timing query requires RenderDoc counter support not exposed through this bridge path."],
        }
        return self._success("get_action_timings", params, data, availability=availability, warnings=warnings)

    def _find_draws_by_shader(self, params: Dict[str, Any]) -> Dict[str, Any]:
        shader_ref = _required_str_param(params, "shader_id" if "shader_id" in params else "shader_ref")
        return self._find_draws("find_draws_by_shader", params, shader_ref, "shader")

    def _find_draws_by_texture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        texture_id = _required_str_param(params, "resource_id" if "resource_id" in params else "texture_id")
        return self._find_draws("find_draws_by_texture", params, texture_id, "resource")

    def _find_draws_by_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resource_id = _required_str_param(params, "resource_id")
        return self._find_draws("find_draws_by_resource", params, resource_id, "resource")

    def _find_draws(self, method: str, params: Dict[str, Any], query: str, ref_kind: str) -> Dict[str, Any]:
        query_norm = _resource_id(query).lower()
        items = []
        for row in self._action_rows():
            refs: List[str] = []
            matched_by = ref_kind
            if ref_kind == "shader":
                refs = list((row.get("shader_refs") or {}).values())
                matched_by = "shader_refs"
            else:
                refs = list(row.get("resource_refs") or [])
                matched_by = "resource_refs"
            for ref in refs:
                if query_norm and query_norm == _resource_id(ref).lower():
                    event_id = row.get("event_id")
                    items.append(
                        {
                            "event_id": event_id,
                            "label": row.get("name", ""),
                            "matched_by": matched_by,
                            "evidence": [{"kind": "event", "id": str(event_id), "label": row.get("name", "")}],
                        }
                    )
                    break
        availability = {"status": "full", "missing_fields": [], "notes": []}
        warnings = []
        if not items:
            availability = {
                "status": "partial",
                "missing_fields": ["actions[].resource_refs" if ref_kind != "shader" else "actions[].shader_refs"],
                "notes": ["No structured refs were matched; current API path may not expose full binding refs."],
            }
            warnings.append("No matches found from bridge-visible action references.")
        data = {"query": query, "match_count": len(items), "items": items}
        return self._success(method, params, data, availability=availability, warnings=warnings)

    def _get_pipeline_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        event_id = _positive_int_param(params, "event_id", -1, minimum=1)
        data, missing = self._pipeline_payload(event_id)
        availability = {"status": "partial" if missing else "full", "missing_fields": sorted(set(missing)), "notes": []}
        warnings = []
        if missing:
            warnings.append("Pipeline state is partial; current bridge path did not expose: %s" % ", ".join(sorted(set(missing))))
        return self._success("get_pipeline_state", params, data, availability=availability, warnings=warnings)

    def _pipeline_payload(self, event_id: int) -> Tuple[Dict[str, Any], List[str]]:
        self._find_action_row(event_id)
        pipe = self._set_event_and_pipeline(event_id)
        shader_refs = self._shader_refs_from_pipeline(pipe)
        data = {
            "event_id": event_id,
            "graphics_api": _jsonable(_attr(pipe, ("graphics_api", "api"), self._graphics_api())),
            "vs_ref": shader_refs.get("vertex", ""),
            "ps_ref": shader_refs.get("pixel", shader_refs.get("fragment", "")),
            "fs_ref": shader_refs.get("fragment", shader_refs.get("pixel", "")),
            "render_target_refs": self._render_target_refs(pipe),
            "depth_target_ref": self._depth_target_ref(pipe),
            "blend": _jsonable(_attr(pipe, ("blend", "blendState"), None)),
            "depth_stencil": _jsonable(_attr(pipe, ("depth_stencil", "depthStencil", "depthState"), None)),
            "rasterizer": _jsonable(_attr(pipe, ("rasterizer", "rasterizerState"), None)),
            "vertex_layout": _jsonable(_attr(pipe, ("vertex_layout", "vertexLayout"), None)),
        }
        missing = []
        for key in ("render_target_refs", "depth_target_ref", "blend", "depth_stencil", "rasterizer", "vertex_layout"):
            value = data.get(key)
            if value is None or value == "" or value == []:
                missing.append(key)
        return data, missing

    def _shader_refs_from_pipeline(self, pipe: Any) -> Dict[str, str]:
        refs = _attr(pipe, ("shaders", "shader_refs", "shaderRefs"), {}) or {}
        if isinstance(refs, dict):
            return {str(stage).lower(): _resource_id(ref) for stage, ref in refs.items() if _resource_id(ref)}
        result: Dict[str, str] = {}
        get_shader = getattr(pipe, "GetShader", None)
        if callable(get_shader):
            for stage in ("vertex", "hull", "domain", "geometry", "pixel", "fragment", "compute"):
                try:
                    ref = _resource_id(get_shader(stage))
                    if ref:
                        result[stage] = ref
                except Exception:
                    pass
        return result

    def _render_target_refs(self, pipe: Any) -> List[str]:
        refs = _attr(pipe, ("render_target_refs", "renderTargets", "output_targets"), None)
        if refs is None:
            try:
                refs = _call_first(pipe, ("GetOutputTargets", "GetRenderTargets"))
            except Exception:
                refs = []
        result = []
        for ref in refs or []:
            rid = _resource_id(_attr(ref, ("resourceId", "resource_id", "id"), ref))
            if rid:
                result.append(rid)
        return result

    def _depth_target_ref(self, pipe: Any) -> Optional[str]:
        ref = _attr(pipe, ("depth_target_ref", "depthTarget", "depth_target"), None)
        if ref is None:
            try:
                ref = _call_first(pipe, ("GetDepthTarget", "GetDepthStencilTarget"))
            except Exception:
                return None
        rid = _resource_id(_attr(ref, ("resourceId", "resource_id", "id"), ref))
        return rid or None

    def _get_shader_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        event_id = _positive_int_param(params, "event_id", -1, minimum=1)
        stage = _required_str_param(params, "stage").lower()
        if stage not in ("vertex", "hull", "domain", "geometry", "pixel", "fragment", "compute"):
            raise BridgeArgumentError("stage must be one of vertex/hull/domain/geometry/pixel/fragment/compute")
        pipe = self._set_event_and_pipeline(event_id)
        shader_refs = self._shader_refs_from_pipeline(pipe)
        shader_ref = shader_refs.get(stage, "")
        if stage == "fragment" and not shader_ref:
            shader_ref = shader_refs.get("pixel", "")
        entry = ""
        try:
            entry = str(_call(pipe, "GetShaderEntryPoint", stage))
        except Exception:
            entry = str(_attr(pipe, ("entry", "entry_point", "entryPoint"), ""))
        missing = []
        warnings = []
        if not shader_ref:
            missing.append("shader_ref")
            warnings.append("No shader reference was exposed for stage=%s at event_id=%d." % (stage, event_id))
        missing.extend(["source", "asm"])
        data = {
            "event_id": event_id,
            "stage": stage,
            "shader_ref": shader_ref,
            "entry": entry,
            "source_available": False,
            "asm_available": False,
        }
        availability = {
            "status": "partial",
            "missing_fields": sorted(set(missing)),
            "notes": ["Shader source/ASM extraction is not exposed by this bridge handler."],
        }
        return self._success("get_shader_info", params, data, availability=availability, warnings=warnings)

    def _get_texture_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resource_id = _required_str_param(params, "resource_id")
        texture = self._find_texture(resource_id)
        data = {
            "resource_id": _resource_id(_attr(texture, ("resourceId", "resource_id", "id"), resource_id)),
            "name": str(_attr(texture, ("name", "customName"), "")),
            "width": _as_int(_attr(texture, ("width",), 0), 0) or 0,
            "height": _as_int(_attr(texture, ("height",), 0), 0) or 0,
            "format": _format_name(_attr(texture, ("format",), "")),
            "sample_count": _as_int(_attr(texture, ("sampleCount", "sample_count", "samples"), 1), 1) or 1,
        }
        return self._success("get_texture_info", params, data)

    def _get_texture_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resource_id = _required_str_param(params, "resource_id")
        max_bytes = _positive_int_param(params, "max_bytes", DEFAULT_MAX_BYTES, minimum=1, maximum=HARD_MAX_BYTES)
        mip = _positive_int_param(params, "mip", 0, minimum=0)
        slice_index = _positive_int_param(params, "slice", 0, minimum=0)
        sample = _positive_int_param(params, "sample", 0, minimum=0)
        texture = self._find_texture(resource_id)
        warnings = []
        availability = {
            "status": "partial",
            "missing_fields": ["texture.data"],
            "notes": ["Texture byte extraction is only available when the controller exposes GetTextureData."],
        }
        data = {
            "resource_id": _resource_id(_attr(texture, ("resourceId", "resource_id", "id"), resource_id)),
            "mip": mip,
            "slice": slice_index,
            "sample": sample,
            "available": False,
            "encoding": "base64",
            "byte_count": 0,
            "truncated": False,
            "payload": "",
        }
        try:
            raw = self._controller_call(lambda controller: _call(controller, "GetTextureData", resource_id, mip, slice_index, sample))
            data.update(self._encoded_payload(raw, max_bytes=max_bytes, encoding="base64"))
            data["available"] = True
            availability = {"status": "full", "missing_fields": [], "notes": []}
            if data["truncated"]:
                warnings.append("Texture payload truncated to max_bytes=%d." % max_bytes)
        except Exception as ex:
            warnings.append("GetTextureData unavailable: %s" % ex)
        return self._success("get_texture_data", params, data, availability=availability, warnings=warnings)

    def _get_buffer_contents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resource_id = _required_str_param(params, "resource_id")
        offset = _positive_int_param(params, "offset", 0, minimum=0)
        byte_count = _positive_int_param(params, "byte_count", DEFAULT_MAX_BYTES, minimum=1, maximum=HARD_MAX_BYTES)
        max_bytes = _positive_int_param(params, "max_bytes", min(byte_count, DEFAULT_MAX_BYTES), minimum=1, maximum=HARD_MAX_BYTES)
        self._find_buffer(resource_id)
        read_count = min(byte_count, max_bytes)
        warnings = []
        availability = {"status": "full", "missing_fields": [], "notes": []}
        try:
            raw = self._controller_call(lambda controller: _call(controller, "GetBufferData", resource_id, offset, read_count))
            data = self._encoded_payload(raw, max_bytes=max_bytes, encoding=str(params.get("encoding", "hex")).lower())
        except Exception as ex:
            data = {
                "available": False,
                "encoding": str(params.get("encoding", "hex")).lower(),
                "byte_count": 0,
                "truncated": False,
                "payload": "",
            }
            availability = {
                "status": "partial",
                "missing_fields": ["buffer.data"],
                "notes": ["Buffer byte extraction is only available when the controller accepts GetBufferData."],
            }
            warnings.append("GetBufferData unavailable: %s" % ex)
        data.update({"resource_id": resource_id, "offset": offset, "requested_byte_count": byte_count})
        if byte_count > max_bytes or data["truncated"]:
            data["truncated"] = True
            warnings.append("Buffer payload truncated to max_bytes=%d." % max_bytes)
        return self._success("get_buffer_contents", params, data, availability=availability, warnings=warnings)

    def _encoded_payload(self, raw: Any, max_bytes: int, encoding: str) -> Dict[str, Any]:
        blob = _bytes_from_result(raw)
        truncated = len(blob) > max_bytes
        payload = blob[:max_bytes]
        if encoding == "base64":
            encoded = base64.b64encode(payload).decode("ascii")
        else:
            encoding = "hex"
            encoded = payload.hex()
        return {
            "available": True,
            "encoding": encoding,
            "byte_count": len(payload),
            "truncated": truncated,
            "payload": encoded,
        }

    def _find_action_row(self, event_id: int) -> Dict[str, Any]:
        for row in self._action_rows():
            if int(row.get("event_id") or 0) == int(event_id):
                return row
        raise BridgeNotFound("event_id not found: %d" % event_id)

    def _find_texture(self, resource_id: str) -> Any:
        needle = _resource_id(resource_id).lower()
        for texture in self._textures():
            rid = _resource_id(_attr(texture, ("resourceId", "resource_id", "id"), ""))
            if rid.lower() == needle:
                return texture
        raise BridgeNotFound("texture resource_id not found: %s" % resource_id)

    def _find_buffer(self, resource_id: str) -> Any:
        needle = _resource_id(resource_id).lower()
        for buffer in self._buffers():
            rid = _resource_id(_attr(buffer, ("resourceId", "resource_id", "id"), ""))
            if rid.lower() == needle:
                return buffer
        raise BridgeNotFound("buffer resource_id not found: %s" % resource_id)

    def _collect_shader_refs(self, rows: List[Dict[str, Any]]) -> List[str]:
        refs = []
        for row in rows:
            refs.extend(list((row.get("shader_refs") or {}).values()))
        return sorted(set(refs))

    def _write_response(self, response: Dict[str, Any]) -> None:
        if not os.path.isdir(self.ipc_dir):
            os.makedirs(self.ipc_dir)
        temp_path = self.response_file + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(_stable_object(response), handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(temp_path, self.response_file)

    def _safe_remove(self, path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass


def start_bridge(context: Any, ipc_dir: Optional[str] = None, poll_interval: float = 0.05) -> RenderDocMCPBridge:
    return RenderDocMCPBridge(context, ipc_dir=ipc_dir, poll_interval=poll_interval).start()
