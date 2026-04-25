# EAP Validator

`eap_validator.py` is a small, local-only validator for Engine Annotation Protocol sidecar files.
It validates one explicit `.rmeta.json` path at a time and reuses the existing MCP sidecar loader for
path, size, JSON, and EAP-shape checks.

The tool is read-only. It does not parse `.rdc` binaries, capture frames, upload files, delete files,
start remote services, or modify annotations.

## Usage

Human-readable summary:

```powershell
py -3 tools\eap_validator\eap_validator.py validate path\to\capture.rmeta.json
```

Machine-readable JSON:

```powershell
py -3 tools\eap_validator\eap_validator.py validate path\to\capture.rmeta.json --json
```

Optional allowlist:

```powershell
py -3 tools\eap_validator\eap_validator.py validate path\to\capture.rmeta.json --allowlist-dir path\to
```

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Sidecar is valid. |
| 1 | CLI usage error. |
| 2 | Sidecar validation failed with a stable loader error code. |

## Output Contract

JSON output uses `schema_version=eap-validator.v1`.

Successful validation returns:

- `ok=true`
- `sidecar.path`
- `sidecar.schema_name`
- `sidecar.schema_version`
- `sidecar.capture_id`
- section counts for render graph nodes, commands, resources, assets, materials, shaders, pipelines,
  and rule results
- provider capabilities inferred from the existing EAP sidecar provider

Validation failure preserves `SidecarLoadError` fields:

- `error.code`
- `error.message`
- `error.path`

## Fixtures

Reusable synthetic fixtures live under `tools/eap_validator/fixtures/`.

| File | Purpose |
|---|---|
| `valid_minimal.rmeta.json` | Smallest useful EAP sidecar shape for loader/validator smoke tests. |
| `valid_fullish.rmeta.json` | Broader synthetic sidecar with render graph, commands, resources, assets, materials, shaders, pipeline, rules, diagnostics, and security sections. |
| `invalid_wrong_schema.rmeta.json` | Non-EAP JSON object used to preserve `invalid_sidecar` behavior. |
| `golden/*.validator.json` | Normalized expected JSON validator output. Tests replace local paths with `<FIXTURE_PATH>` before comparison. |

The fixtures are synthetic and intentionally do not include real captures, private asset paths, shader
source, screenshots, or `.rdc` binary data.
