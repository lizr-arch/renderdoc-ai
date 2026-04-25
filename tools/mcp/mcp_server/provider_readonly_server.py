from __future__ import annotations

from typing import Any, Mapping, Optional

from providers import ProviderContext, build_default_registry  # type: ignore

from .provider_tools import (
    DEFAULT_MAX_BYTES,
    load_eap_sidecar_envelope,
    parse_allowlist_env,
)


def _import_fastmcp() -> Any:
    from mcp.server.fastmcp import FastMCP

    return FastMCP


def create_mcp_server(
    *,
    fastmcp_cls: Optional[Any] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Any:
    cls = fastmcp_cls or _import_fastmcp()
    mcp = cls(
        "RenderDoc Provider Readonly",
        instructions=(
            "Read-only RenderDoc provider availability tools. "
            "Does not open RDC files, generate reports, execute commands, or scan directories."
        ),
    )

    @mcp.tool()
    def get_data_availability() -> dict:
        return build_default_registry().data_availability(ProviderContext()).as_dict()

    @mcp.tool()
    def load_eap_sidecar(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
        return load_eap_sidecar_envelope(
            path,
            allowlist_dirs=parse_allowlist_env(env),
            max_bytes=max_bytes,
        )

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
