from __future__ import annotations

from typing import Any, Mapping, Optional

from providers import ProviderContext, build_default_registry  # type: ignore

from .provider_tools import (
    DEFAULT_MAX_BYTES,
    DEFAULT_SEARCH_LIMIT,
    get_eap_rule_results_envelope,
    load_eap_sidecar_envelope,
    parse_allowlist_env,
    search_eap_commands_envelope,
    summarize_eap_sidecar_envelope,
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

    @mcp.tool()
    def summarize_eap_sidecar(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
        return summarize_eap_sidecar_envelope(
            path,
            allowlist_dirs=parse_allowlist_env(env),
            max_bytes=max_bytes,
        )

    @mcp.tool()
    def search_eap_commands(
        path: str,
        query: str = "",
        pass_id: str = "",
        resource_id: str = "",
        material_id: str = "",
        shader_id: str = "",
        pipeline_id: str = "",
        limit: int = DEFAULT_SEARCH_LIMIT,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict:
        return search_eap_commands_envelope(
            path,
            query=query,
            pass_id=pass_id,
            resource_id=resource_id,
            material_id=material_id,
            shader_id=shader_id,
            pipeline_id=pipeline_id,
            limit=limit,
            allowlist_dirs=parse_allowlist_env(env),
            max_bytes=max_bytes,
        )

    @mcp.tool()
    def get_eap_rule_results(
        path: str,
        severity: str = "",
        limit: int = DEFAULT_SEARCH_LIMIT,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict:
        return get_eap_rule_results_envelope(
            path,
            severity=severity,
            limit=limit,
            allowlist_dirs=parse_allowlist_env(env),
            max_bytes=max_bytes,
        )

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
