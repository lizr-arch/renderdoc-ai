# EAP Scout CLI

EAP Scout is the first tooling step for Engine Annotation Protocol repository reconnaissance.
It is built for the case where the current RenderDoc workspace is not the game engine repository,
but we still need a repeatable way to scan external game or engine source trees and generate an
implementation plan.

It does not modify the scanned repository. It does not implement `RenderDocBridge`, EAP runtime
types, sidecar metadata writing, MCP servers, or analyzer rules. It only produces reports and
evidence that make the next Codex task smaller and safer.

## Tool Position

Use EAP Scout when:

- The real game repository and game-engine repository are outside this RenderDoc checkout.
- You need to identify RHI, render graph, GPU marker, draw/dispatch, resource, shader, material,
  mesh, PSO, build-system, config, and test candidates.
- You need a copyable `codex_next_prompt.md` that tells the next agent what to inspect and what not
  to modify.

Do not use EAP Scout as:

- A RenderDoc core modification path.
- A runtime annotation emitter.
- A sidecar writer.
- A build or dependency installer.
- A network scanner.

## Command Usage

Scan one repository:

```bash
python tools/eap_scout/eap_scout.py scan --repo F:\Code\S1 --out .tmp\eap_scout_game
```

Scan an engine repository:

```bash
python tools/eap_scout/eap_scout.py scan --repo E:\Code\GIT\s1 --out .tmp\eap_scout_engine --engine custom
```

Limit scan volume:

```bash
python tools/eap_scout/eap_scout.py scan --repo E:\Code\GIT\s1 --out .tmp\eap_scout_engine_small --max-files 5000
```

Generate a prompt from an existing manifest:

```bash
python tools/eap_scout/eap_scout.py prompt --manifest .tmp\eap_scout_engine\eap_repo_manifest.json --task renderdoc_bridge --out .tmp\eap_scout_engine\next_prompt.md
```

Summarize several report directories:

```bash
python tools/eap_scout/eap_scout.py summarize --reports .tmp --out .tmp\eap_scout_summary.json
```

## Output Files

`scan` writes:

- `eap_repo_manifest.json`: machine-readable schema `eap_scout_manifest.v1`.
- `EAP_IMPLEMENTATION_MAP.md`: planning report with the standard 13 EAP implementation sections.
- `EAP_HOOK_CANDIDATES.md`: grouped hook candidates for RenderDoc, RHI, render graph, draw/dispatch,
  resources, shader/material/mesh/PSO, config/CVar, and tests.
- `codex_next_prompt.md`: next-task prompt generated from the scan result.
- `evidence/repo_inventory.json`: inventory and repository-type evidence.
- `evidence/build_system_hits.json`: build-system and module descriptor candidates.
- `evidence/renderdoc_hits.json`: existing RenderDoc integration evidence.
- `evidence/rendergraph_hits.json`: render graph/pass evidence.
- `evidence/rhi_hits.json`: RHI, command-list, and command-buffer evidence.
- `evidence/marker_hits.json`: GPU marker/debug marker evidence.
- `evidence/resource_hits.json`: texture, buffer, asset, and streaming evidence.
- `evidence/shader_material_mesh_hits.json`: shader, material, mesh, PSO, draw, and dispatch evidence.
- `evidence/test_hits.json`: unit/integration/tool test evidence.

## Scanning Multiple Projects

Run one scan per repository and keep outputs separate:

```bash
python tools/eap_scout/eap_scout.py scan --repo F:\Code\S1 --out .tmp\eap_scout\S1_game
python tools/eap_scout/eap_scout.py scan --repo E:\Code\GIT\s1 --out .tmp\eap_scout\s1_engine
python tools/eap_scout/eap_scout.py summarize --reports .tmp\eap_scout --out .tmp\eap_scout\summary.json
```

Compare the recommendations:

- A RenderDoc fork should recommend `RepoReconOnly` and set
  `is_wrong_repo_for_engine_emission=true`.
- A game project without renderer ownership should recommend `EngineModuleSelection`.
- An engine repository with RHI/render graph/GPU marker evidence should recommend
  `RenderDocBridge MVP`.
- A repository with an existing RenderDoc bridge but no EAP core should recommend `EAPCoreTypes`.

## Feeding Codex

After a scan, open or paste `codex_next_prompt.md` into the next Codex session. Keep the generated
manifest and evidence JSON available in the same output directory. The prompt is intentionally
strict:

- For a RenderDoc fork, it forbids engine-side bridge implementation.
- For an engine repository, it lists recommended directories to inspect first and forbidden
  directories/actions.
- For low-confidence scans, it requires manual ownership confirmation before writing runtime code.

## Limitations

- The scanner is keyword and pattern based; it is not a compiler, language server, or full AST
  analyzer.
- It cannot prove that a candidate is the correct owner of a hook; it only records evidence.
- Documentation/planning folders, generated code, wrappers, and vendor code are skipped or
  down-scoped by path rules.
- Local Codex scratch/cache folders and generated output directories are skipped so scanner
  self-tests do not recurse into nested worktrees or historical report artifacts.
- It does not inspect binary assets, shader bytecode, or compiled metadata.
- It does not require RenderDoc, and therefore cannot validate RenderDoc API availability.
- It does not verify that the target repository builds.

## Safety Notes

- Always scan to an output directory outside the target repository when possible.
- Treat asset paths and project paths in evidence as potentially sensitive.
- Do not implement EAP emission in a `renderdoc_fork` scan result.
- Do not write runtime code from a low-confidence scan without human confirmation.
- Keep shipping builds disabled for future EAP emission work.
- Preserve the target repository: no cloning, deleting, moving, formatting, or dependency changes
  are part of this CLI.
