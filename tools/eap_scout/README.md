# EAP Scout

EAP Scout is a small, local-only reconnaissance CLI for Engine Annotation Protocol planning.
It scans a game or engine repository and writes a manifest, Markdown reports, next-task prompt,
and evidence JSON that can be handed to Codex before any runtime EAP implementation starts.

The scanner is intentionally read-only for the target repository. It does not require RenderDoc to
be installed, does not build the target project, and does not implement a RenderDoc bridge, EAP
runtime, sidecar writer, MCP server, or rule engine.

## Commands

Scan a repository:

```bash
python tools/eap_scout/eap_scout.py scan --repo <path> --out <path> [--engine auto|unreal|unity|custom] [--max-files N]
```

Generate a next Codex prompt from an existing manifest:

```bash
python tools/eap_scout/eap_scout.py prompt --manifest <path>/eap_repo_manifest.json --task renderdoc_bridge --out <path>
```

Summarize one or more scan outputs:

```bash
python tools/eap_scout/eap_scout.py summarize --reports <dir> --out <path>
```

## Outputs

`scan` writes these files under `--out`:

- `eap_repo_manifest.json`: structured scan result and recommendation.
- `EAP_IMPLEMENTATION_MAP.md`: implementation map using the EAP planning sections.
- `EAP_HOOK_CANDIDATES.md`: grouped hook candidates by concept.
- `codex_next_prompt.md`: copyable prompt for the next Codex task.
- `evidence/*.json`: focused evidence payloads for repository inventory, build systems,
  RenderDoc integration, render graph, RHI, markers, resources, shader/material/mesh/PSO,
  and tests.

## Scan Policy

EAP Scout uses only Python standard library APIs. It walks local files with a conservative allowlist
of source/config extensions, skips binary or oversized files, and records skipped-file reasons in
the manifest. By default it skips files over 2 MB and scans at most 30000 files.

Ignored directories include `.git`, local Codex scratch/cache folders, documentation/planning
folders, generated outputs, build outputs, `node_modules`, common third-party/vendor folders,
Unreal generated folders, and Unity cache folders.

## Repository Classification

The scanner estimates a repository type from file layout and concept evidence:

- `renderdoc_fork`: RenderDoc source/tooling workspace. Do not implement engine-side EAP emission.
- `game_engine_repo`: engine or renderer repository with RHI/render graph/marker evidence.
- `unreal_project_or_plugin`: Unreal project/plugin markers without enough engine ownership evidence.
- `unity_project`: Unity project markers.
- `game_project_repo`: game content/scripts without renderer/RHI ownership.
- `unknown`: insufficient evidence.

Recommendations are deliberately conservative. Low-confidence scans should be followed by manual
module ownership confirmation before code changes.

## Development Notes

Rules live in `tools/eap_scout/rules/`. Templates live in `tools/eap_scout/templates/`.
Tests use Python `unittest` and small in-memory fixtures:

```bash
python -m unittest discover tools/eap_scout/tests
```
