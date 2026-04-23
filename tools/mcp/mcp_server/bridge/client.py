"""
RenderDoc Bridge Client
Communicates with the RenderDoc extension via file-based IPC.
"""

import json
import os
import tempfile
import time
import uuid
from typing import Any


# IPC directory (must match renderdoc_extension/socket_server.py)
IPC_DIR = os.path.join(tempfile.gettempdir(), "renderdoc_mcp")
REQUEST_FILE = os.path.join(IPC_DIR, "request.json")
RESPONSE_FILE = os.path.join(IPC_DIR, "response.json")
LOCK_FILE = os.path.join(IPC_DIR, "lock")


class RenderDocBridgeError(Exception):
    """Error communicating with RenderDoc bridge"""

    pass


class RenderDocBridge:
    """Client for communicating with RenderDoc extension via file-based IPC"""

    def __init__(self, host: str = "127.0.0.1", port: int = 19876):
        # host/port are kept for API compatibility but not used
        self.host = host
        self.port = port
        self.timeout = 30.0  # seconds

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Call a method on the RenderDoc extension"""
        # Check if IPC directory exists
        if not os.path.exists(IPC_DIR):
            raise RenderDocBridgeError(
                f"Cannot connect to RenderDoc MCP Bridge at {self.host}:{self.port}. "
                "Make sure RenderDoc is running with the MCP Bridge extension loaded."
            )

        initial_state = _inspect_ipc_state()
        request = {
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }

        try:
            # Clean up any stale response file
            if os.path.exists(RESPONSE_FILE):
                os.remove(RESPONSE_FILE)

            # Create lock file to signal we're writing
            with open(LOCK_FILE, "w") as f:
                f.write("lock")

            # Write request
            with open(REQUEST_FILE, "w", encoding="utf-8") as f:
                json.dump(request, f)

            # Remove lock file to signal write complete
            os.remove(LOCK_FILE)

            # Wait for response
            start_time = time.time()
            while True:
                if os.path.exists(RESPONSE_FILE):
                    # Small delay to ensure file is fully written
                    time.sleep(0.01)

                    # Read response
                    with open(RESPONSE_FILE, "r", encoding="utf-8") as f:
                        response = json.load(f)

                    # Clean up response file
                    os.remove(RESPONSE_FILE)

                    if "error" in response:
                        error = response["error"]
                        raise RenderDocBridgeError(f"[{error['code']}] {error['message']}")

                    return response.get("result")

                # Check timeout
                if time.time() - start_time > self.timeout:
                    current_state = _inspect_ipc_state()
                    raise RenderDocBridgeError(
                        "Request timed out while waiting for RenderDoc MCP response. "
                        f"{_format_ipc_state_summary(current_state, prefix='current')}; "
                        f"{_format_ipc_state_summary(initial_state, prefix='preexisting')}"
                    )

                # Poll interval
                time.sleep(0.05)

        except RenderDocBridgeError:
            raise
        except Exception as e:
            raise RenderDocBridgeError(f"Communication error: {e}")


def _inspect_ipc_state() -> dict[str, Any]:
    state = {
        "ipc_dir_exists": os.path.isdir(IPC_DIR),
        "request_present": os.path.exists(REQUEST_FILE),
        "response_present": os.path.exists(RESPONSE_FILE),
        "lock_present": os.path.exists(LOCK_FILE),
        "request_age_seconds": _file_age_seconds(REQUEST_FILE),
        "response_age_seconds": _file_age_seconds(RESPONSE_FILE),
    }
    return state


def _format_ipc_state_summary(state: dict[str, Any], *, prefix: str) -> str:
    parts: list[str] = []
    for key in (
        "ipc_dir_exists",
        "request_present",
        "response_present",
        "lock_present",
        "request_age_seconds",
        "response_age_seconds",
    ):
        value = state.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, float):
            rendered = f"{value:.3f}"
        else:
            rendered = str(value)
        parts.append(f"{prefix}_{key}={rendered}")
    return "; ".join(parts)


def _file_age_seconds(path: str) -> float | None:
    try:
        if not os.path.exists(path):
            return None
        return max(0.0, time.time() - os.path.getmtime(path))
    except Exception:
        return None
