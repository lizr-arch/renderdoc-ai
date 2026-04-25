#!/usr/bin/env python
"""EAP Scout CLI.

Scans a local game or engine repository and emits an Engine Annotation Protocol
implementation map without modifying the scanned repository.
"""

from __future__ import print_function

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = "eap_scout_manifest.v1"
DEFAULT_MAX_FILES = 30000
DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_IGNORED_DIR_COUNT = 5000
TOOL_ROOT = Path(__file__).resolve().parent

DEFAULT_IGNORED_DIRS = {
    ".git",
    ".tmp",
    ".codex_repos",
    ".codex_worktrees",
    ".codex",
    ".codemaker",
    ".pytest_cache",
    ".sdd",
    ".serena",
    ".tmp-gh-config",
    ".uv-cache",
    ".uv-cache-codex",
    "__pycache__",
    "build",
    "bin",
    "obj",
    "docs",
    "documentation",
    "plans",
    "dist",
    "out",
    "output",
    "logs",
    "node_modules",
    "thirdparty",
    "third_party",
    "3rdparty",
    "external",
    "extern",
    "intermediate",
    "saved",
    "deriveddatacache",
    "library",
    "temp",
    "stress_test_output",
    "test_bundle_cli",
    "test_output",
    "x64",
}

DEFAULT_SOURCE_EXTENSIONS = {
    ".h",
    ".hpp",
    ".hh",
    ".cpp",
    ".cc",
    ".c",
    ".cs",
    ".mm",
    ".m",
    ".py",
    ".lua",
    ".json",
    ".xml",
    ".uproject",
    ".uplugin",
    ".cmake",
}

DEFAULT_SOURCE_NAMES = {
    "cmakelists.txt",
    "premake5.lua",
    "sconstruct",
    "sconscript",
    "makefile",
    "workspace",
    "build.bazel",
}

CONCEPT_NAMES = [
    "repo_type",
    "build_system",
    "renderdoc_integration",
    "rhi",
    "command_list",
    "command_buffer",
    "render_graph",
    "gpu_marker",
    "draw",
    "dispatch",
    "texture",
    "buffer",
    "shader",
    "material",
    "mesh",
    "pso",
    "asset",
    "streaming",
    "config",
    "console_variable",
    "tests",
]

EVIDENCE_FILES = {
    "repo_inventory.json": ["repo_type"],
    "build_system_hits.json": ["build_system"],
    "renderdoc_hits.json": ["renderdoc_integration"],
    "rendergraph_hits.json": ["render_graph"],
    "rhi_hits.json": ["rhi", "command_list", "command_buffer"],
    "marker_hits.json": ["gpu_marker"],
    "resource_hits.json": ["texture", "buffer", "resource", "asset", "streaming"],
    "shader_material_mesh_hits.json": ["shader", "material", "mesh", "pso", "draw", "dispatch"],
    "test_hits.json": ["tests"],
}


def normalize_path(path):
    """Return a stable slash-separated path string."""
    return str(path).replace("\\", "/")


def safe_resolve(path):
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path).absolute()


def utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def increment(mapping, key, amount=1):
    mapping[key] = mapping.get(key, 0) + amount


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Scan repositories for EAP integration points.")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="scan a local game or engine repository")
    scan.add_argument("--repo", required=True, help="repository path to scan")
    scan.add_argument("--out", required=True, help="output directory")
    scan.add_argument("--engine", default="auto", choices=["auto", "unreal", "unity", "custom"])
    scan.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)

    prompt = sub.add_parser("prompt", help="generate next Codex prompt from a manifest")
    prompt.add_argument("--manifest", required=True, help="path to eap_repo_manifest.json")
    prompt.add_argument("--task", default="renderdoc_bridge", choices=["renderdoc_bridge"])
    prompt.add_argument("--out", required=True, help="prompt file or output directory")

    summarize = sub.add_parser("summarize", help="summarize one or more EAP scout reports")
    summarize.add_argument("--reports", required=True, help="directory containing reports")
    summarize.add_argument("--out", required=True, help="summary file or output directory")

    return parser.parse_args(argv)


def read_json_file(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_rules(rules_dir=None):
    """Load JSON concept rules, with a small built-in fallback for robustness."""
    rules_path = Path(rules_dir) if rules_dir else TOOL_ROOT / "rules"
    rules = {}
    settings = {
        "ignored_dirs": sorted(DEFAULT_IGNORED_DIRS),
        "source_extensions": sorted(DEFAULT_SOURCE_EXTENSIONS),
        "source_names": sorted(DEFAULT_SOURCE_NAMES),
        "max_file_size": DEFAULT_MAX_FILE_SIZE,
    }

    if rules_path.exists():
        for path in sorted(rules_path.rglob("*.json")):
            try:
                data = read_json_file(path)
            except (IOError, ValueError):
                continue

            if "settings" in data:
                for key, value in data["settings"].items():
                    settings[key] = value

            if "concepts" in data:
                for name, rule in data["concepts"].items():
                    rule = dict(rule)
                    rule["concept"] = name
                    rules[name] = normalize_rule(rule)

            if "concept" in data:
                rules[data["concept"]] = normalize_rule(data)

    for name, rule in builtin_rules().items():
        if name not in rules:
            rules[name] = normalize_rule(rule)

    for name in CONCEPT_NAMES:
        if name not in rules:
            rules[name] = normalize_rule({"concept": name, "keywords": [], "patterns": []})

    return {"settings": settings, "concepts": rules}


def normalize_rule(rule):
    normalized = {
        "concept": rule.get("concept", ""),
        "keywords": list(rule.get("keywords", [])),
        "patterns": list(rule.get("patterns", [])),
        "path_hints": list(rule.get("path_hints", [])),
        "reason": rule.get("reason", "Keyword or path evidence suggests this concept."),
        "risk": rule.get("risk", "Candidate must be validated against real ownership before code changes."),
        "recommended_eap_usage": rule.get(
            "recommended_eap_usage",
            "Use as evidence for EAP placement, not as an automatic edit target.",
        ),
        "min_score": float(rule.get("min_score", 0.25)),
    }
    compiled = []
    for item in normalized["patterns"]:
        if isinstance(item, str):
            compiled.append({"name": item, "regex": item})
        else:
            compiled.append({"name": item.get("name", item.get("regex", "")), "regex": item.get("regex", "")})
    normalized["patterns"] = compiled
    compiled_regexes = []
    for item in compiled:
        try:
            compiled_regexes.append((item.get("name", item.get("regex", "")), re.compile(item.get("regex", ""), re.IGNORECASE)))
        except re.error:
            continue
    normalized["_compiled_patterns"] = compiled_regexes
    return normalized


def builtin_rules():
    return {
        "build_system": {
            "concept": "build_system",
            "keywords": ["cmakelists", "premake", "sconstruct", ".build.cs", "target.cs", "build.bazel"],
            "patterns": [{"name": "cmake", "regex": r"\b(project|add_library|add_executable|cmake_minimum_required)\b"}],
            "path_hints": ["CMakeLists.txt", ".uproject", ".uplugin", ".build.cs", "premake5.lua"],
        },
        "renderdoc_integration": {
            "concept": "renderdoc_integration",
            "keywords": ["renderdoc_app.h", "RENDERDOC_GetAPI", "SetObjectAnnotation", "SetCommandAnnotation"],
            "patterns": [{"name": "renderdoc dll", "regex": r"renderdoc\.(dll|so|dylib)"}],
            "path_hints": ["renderdoc_app.h", "renderdoc"],
        },
        "rhi": {
            "concept": "rhi",
            "keywords": ["RHI", "RHIDevice", "RHICommandList", "GraphicsDevice", "RenderDevice"],
            "patterns": [{"name": "rhi command list", "regex": r"\b(RHI|Graphics|Render).*(Device|Command|Queue)\b"}],
            "path_hints": ["RHI", "Renderer", "Render"],
        },
        "render_graph": {
            "concept": "render_graph",
            "keywords": ["RenderGraph", "AddPass", "ExecutePass", "RenderPass", "FrameGraph"],
            "patterns": [{"name": "add pass", "regex": r"\b(AddPass|ExecutePass|RenderGraph|FrameGraph)\b"}],
            "path_hints": ["RenderGraph", "FrameGraph"],
        },
        "gpu_marker": {
            "concept": "gpu_marker",
            "keywords": ["BeginGpuMarker", "EndGpuMarker", "PushDebugGroup", "PopDebugGroup", "PIXBeginEvent"],
            "patterns": [{"name": "gpu marker", "regex": r"\b(Begin|Push|Start).*(GPU|Gpu|Debug|Marker|Event)\b"}],
            "path_hints": ["Marker", "Profiler", "Debug"],
        },
    }


def is_ignored_dir(name, ignored_dirs):
    return name.lower() in ignored_dirs


def count_files_in_tree(root, ignored_dirs, limit=MAX_IGNORED_DIR_COUNT):
    total = 0
    for current, dirs, files in os.walk(str(root)):
        dirs[:] = [d for d in dirs if not is_ignored_dir(d, ignored_dirs)]
        total += len(files)
        if total >= limit:
            return limit
    return total or 1


def is_supported_source(path, source_extensions, source_names):
    name = path.name.lower()
    if name in source_names:
        return True
    if name.endswith(".build.cs"):
        return True
    return path.suffix.lower() in source_extensions


def language_for(path):
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.endswith(".build.cs") or suffix == ".cs":
        return "csharp"
    if suffix in (".cpp", ".cc", ".cxx", ".mm"):
        return "cpp"
    if suffix in (".h", ".hpp", ".hh"):
        return "cpp_header"
    if suffix == ".c":
        return "c"
    if suffix == ".py":
        return "python"
    if suffix == ".lua":
        return "lua"
    if suffix in (".json", ".uproject", ".uplugin"):
        return "json"
    if suffix == ".xml":
        return "xml"
    if suffix == ".cmake" or name == "cmakelists.txt":
        return "cmake"
    return suffix.lstrip(".") or "unknown"


def detect_build_system(path):
    lower = path.name.lower()
    rel = normalize_path(path).lower()
    hits = []
    if lower == "cmakelists.txt" or lower.endswith(".cmake"):
        hits.append("cmake")
    if lower.endswith(".sln") or lower.endswith(".vcxproj"):
        hits.append("msbuild")
    if lower == "premake5.lua":
        hits.append("premake")
    if lower in ("sconstruct", "sconscript"):
        hits.append("scons")
    if lower in ("build.bazel", "workspace") or "bazel" in rel:
        hits.append("bazel")
    if lower.endswith(".uproject") or lower.endswith(".uplugin") or lower.endswith(".build.cs") or lower.endswith(".target.cs"):
        hits.append("unreal_build_tool")
    if lower == "package.json":
        hits.append("node")
    if lower in ("pyproject.toml", "setup.py"):
        hits.append("python")
    return hits


def collect_renderdoc_fast_files(repo):
    markers = [
        repo / "renderdoc" / "api" / "app" / "renderdoc_app.h",
        repo / "renderdoc" / "replay" / "app_api.cpp",
    ]
    marker_score = sum(1 for path in markers if path.exists())
    if (repo / "qrenderdoc").is_dir():
        marker_score += 1
    if (repo / "renderdoccmd").is_dir():
        marker_score += 1
    if marker_score < 3:
        return []

    files = []
    for path in markers:
        if path.exists():
            files.append(path)
    for rel in [
        "CMakeLists.txt",
        "renderdoc.sln",
        "qrenderdoc/qrenderdoc.pro",
        "renderdoccmd/renderdoccmd.cpp",
    ]:
        path = repo / rel
        if path.exists() and path.is_file():
            files.append(path)
    return files


def read_text_file(path, max_size):
    try:
        size = path.stat().st_size
    except OSError:
        return None, "stat_error"
    if size > max_size:
        return None, "too_large"
    try:
        with open(str(path), "rb") as handle:
            raw = handle.read()
    except IOError:
        return None, "read_error"
    if b"\x00" in raw[:4096]:
        return None, "binary"
    return raw.decode("utf-8", errors="replace"), None


def scan_single_file(repo, path, text, concepts, rules, inventory):
    try:
        rel_path = normalize_path(path.relative_to(repo))
    except ValueError:
        rel_path = normalize_path(path)

    if rel_path not in inventory["sample_files"] and len(inventory["sample_files"]) < 200:
        inventory["sample_files"].append(rel_path)

    for build in detect_build_system(path):
        increment(inventory["build_systems"], build)

    increment(inventory["languages"], language_for(path))
    lower_text = text.lower()
    for concept_name, rule in rules.items():
        if concept_name not in concepts:
            continue
        candidate = scan_concept(rule, rel_path, text, lower_text)
        if candidate:
            add_candidate(concepts, concept_name, candidate)


def truncate_text(text, limit=240):
    cleaned = " ".join(text.strip().split())
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def score_candidate(rule, matched_keywords, matched_patterns, path_matches, evidence_count):
    score = 0.0
    score += min(0.48, 0.13 * len(matched_keywords))
    score += min(0.38, 0.21 * len(matched_patterns))
    score += min(0.25, 0.08 * len(path_matches))
    if evidence_count:
        score += min(0.15, 0.04 * evidence_count)
    return min(1.0, round(score, 3))


def scan_concept(rule, rel_path, text, lower_text=None, lines=None):
    lower_path = rel_path.lower()
    path_matches = []
    for hint in rule.get("path_hints", []):
        if hint.lower() in lower_path:
            path_matches.append(hint)

    keywords = rule.get("keywords", [])
    keyword_lowers = [(keyword, keyword.lower()) for keyword in keywords]
    regexes = rule.get("_compiled_patterns", [])

    if lower_text is None:
        lower_text = text.lower()
    active_keywords = [(keyword, keyword_lower) for keyword, keyword_lower in keyword_lowers if keyword_lower in lower_text]
    if not path_matches and not active_keywords:
        return None
    active_regexes = [(name, regex) for name, regex in regexes if regex.search(text)]
    if path_matches and not active_keywords and not active_regexes:
        evidence_lines = [{"line": 0, "text": "path hint: " + rel_path}]
        score = score_candidate(rule, [], [], path_matches, len(evidence_lines))
        if score < rule.get("min_score", 0.25):
            return None
        return {
            "path": rel_path,
            "score": score,
            "matched_keywords": [],
            "matched_patterns": [],
            "evidence_lines": evidence_lines,
            "reason": "path hints: " + ", ".join(path_matches[:6]),
            "risk": rule.get("risk", ""),
            "recommended_eap_usage": rule.get("recommended_eap_usage", ""),
        }

    matched_keywords = set([keyword for keyword, _keyword_lower in active_keywords])
    matched_patterns = set([name for name, _regex in active_regexes])
    evidence_lines = []
    if lines is None:
        lines = text.splitlines()

    for line_no, line in enumerate(lines, 1):
        if len(evidence_lines) >= 10:
            break
        lower_line = line.lower()
        line_matched = False
        for keyword, keyword_lower in active_keywords:
            if keyword_lower and keyword_lower in lower_line:
                line_matched = True
        for name, regex in active_regexes:
            if regex.search(line):
                line_matched = True
        if line_matched:
            evidence_lines.append({"line": line_no, "text": truncate_text(line)})

    if not evidence_lines and path_matches:
        evidence_lines.append({"line": 0, "text": "path hint: " + rel_path})

    score = score_candidate(rule, matched_keywords, matched_patterns, path_matches, len(evidence_lines))
    if score < rule.get("min_score", 0.25):
        return None

    matched_keywords = sorted(matched_keywords)
    matched_patterns = sorted(matched_patterns)
    reason_bits = []
    if matched_keywords:
        reason_bits.append("keywords: " + ", ".join(matched_keywords[:6]))
    if matched_patterns:
        reason_bits.append("patterns: " + ", ".join(matched_patterns[:6]))
    if path_matches:
        reason_bits.append("path hints: " + ", ".join(path_matches[:6]))

    return {
        "path": rel_path,
        "score": score,
        "matched_keywords": matched_keywords,
        "matched_patterns": matched_patterns,
        "evidence_lines": evidence_lines[:10],
        "reason": "; ".join(reason_bits) if reason_bits else rule.get("reason", ""),
        "risk": rule.get("risk", ""),
        "recommended_eap_usage": rule.get("recommended_eap_usage", ""),
    }


def make_empty_concepts():
    return {
        name: {"status": "not_found", "confidence": 0.0, "candidates": []}
        for name in CONCEPT_NAMES
    }


def add_candidate(concepts, concept_name, candidate):
    if concept_name not in concepts:
        concepts[concept_name] = {"status": "not_found", "confidence": 0.0, "candidates": []}
    concepts[concept_name]["candidates"].append(candidate)


def finalize_concepts(concepts):
    for name, data in concepts.items():
        candidates = sorted(data.get("candidates", []), key=lambda c: (-c.get("score", 0.0), c.get("path", "")))
        candidates = candidates[:25]
        confidence = 0.0
        if candidates:
            confidence = min(1.0, candidates[0].get("score", 0.0) + min(0.2, 0.02 * (len(candidates) - 1)))
        confidence = round(confidence, 3)
        if confidence >= 0.55:
            status = "found"
        elif confidence >= 0.25:
            status = "maybe"
        else:
            status = "not_found"
        data["candidates"] = candidates
        data["confidence"] = confidence
        data["status"] = status


def scan_repo(repo_path, max_files=DEFAULT_MAX_FILES, engine="auto"):
    repo = safe_resolve(repo_path)
    rules_bundle = load_rules()
    settings = rules_bundle["settings"]
    rules = rules_bundle["concepts"]

    ignored_dirs = set([str(d).lower() for d in settings.get("ignored_dirs", sorted(DEFAULT_IGNORED_DIRS))])
    source_extensions = set([str(ext).lower() for ext in settings.get("source_extensions", sorted(DEFAULT_SOURCE_EXTENSIONS))])
    source_names = set([str(name).lower() for name in settings.get("source_names", sorted(DEFAULT_SOURCE_NAMES))])
    max_file_size = int(settings.get("max_file_size", DEFAULT_MAX_FILE_SIZE))

    scan = {
        "files_seen": 0,
        "files_scanned": 0,
        "files_skipped": 0,
        "skip_reasons": {},
        "max_files": int(max_files),
    }
    inventory = {
        "root": normalize_path(repo),
        "top_dirs": [],
        "sample_files": [],
        "languages": {},
        "build_systems": {},
        "engine_hint": engine,
    }
    concepts = make_empty_concepts()

    if not repo.exists() or not repo.is_dir():
        scan["files_skipped"] = 1
        increment(scan["skip_reasons"], "repo_not_found")
        manifest = build_manifest(repo, scan, inventory, concepts, engine)
        return manifest

    try:
        inventory["top_dirs"] = sorted([p.name for p in repo.iterdir() if p.is_dir()])[:100]
    except OSError:
        inventory["top_dirs"] = []

    fast_files = collect_renderdoc_fast_files(repo)
    if fast_files:
        for path in fast_files:
            scan["files_seen"] += 1
            text, error = read_text_file(path, max_file_size)
            if error:
                scan["files_skipped"] += 1
                increment(scan["skip_reasons"], error)
                continue
            scan["files_scanned"] += 1
            scan_single_file(repo, path, text, concepts, rules, inventory)
        finalize_concepts(concepts)
        manifest = build_manifest(repo, scan, inventory, concepts, engine)
        return manifest

    for current, dirs, files in os.walk(str(repo)):
        current_path = Path(current)
        kept_dirs = []
        for dirname in sorted(dirs):
            if is_ignored_dir(dirname, ignored_dirs):
                ignored_path = current_path / dirname
                count = count_files_in_tree(ignored_path, ignored_dirs)
                scan["files_seen"] += count
                scan["files_skipped"] += count
                increment(scan["skip_reasons"], "ignored_dir:" + dirname, count)
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        sorted_files = sorted(files)
        for index, filename in enumerate(sorted_files):
            if scan["files_scanned"] >= max_files:
                remaining = len(sorted_files) - index
                scan["files_seen"] += remaining
                scan["files_skipped"] += remaining
                increment(scan["skip_reasons"], "max_files", remaining)
                dirs[:] = []
                break

            path = current_path / filename
            scan["files_seen"] += 1
            try:
                rel_path = normalize_path(path.relative_to(repo))
            except ValueError:
                rel_path = normalize_path(path)

            if len(inventory["sample_files"]) < 200:
                inventory["sample_files"].append(rel_path)

            for build in detect_build_system(path):
                increment(inventory["build_systems"], build)

            if not is_supported_source(path, source_extensions, source_names):
                scan["files_skipped"] += 1
                increment(scan["skip_reasons"], "unsupported_extension")
                continue

            if scan["files_scanned"] >= max_files:
                scan["files_skipped"] += 1
                increment(scan["skip_reasons"], "max_files")
                continue

            text, error = read_text_file(path, max_file_size)
            if error:
                scan["files_skipped"] += 1
                increment(scan["skip_reasons"], error)
                continue

            scan["files_scanned"] += 1
            scan_single_file(repo, path, text, concepts, rules, inventory)

    finalize_concepts(concepts)
    manifest = build_manifest(repo, scan, inventory, concepts, engine)
    return manifest


def path_marker(inventory, suffix):
    suffix = suffix.lower()
    for path in inventory.get("sample_files", []):
        if path.lower().endswith(suffix):
            return True
    return False


def top_dir_marker(inventory, name):
    return name.lower() in set([d.lower() for d in inventory.get("top_dirs", [])])


def classify_repo(inventory, concepts, engine="auto"):
    notes = []
    renderdoc_markers = [
        path_marker(inventory, "renderdoc/api/app/renderdoc_app.h"),
        path_marker(inventory, "renderdoc/replay/app_api.cpp"),
        top_dir_marker(inventory, "qrenderdoc"),
        top_dir_marker(inventory, "renderdoccmd"),
    ]
    renderdoc_score = sum(1 for item in renderdoc_markers if item)

    if renderdoc_score >= 3:
        return "renderdoc_fork", round(0.75 + 0.05 * renderdoc_score, 3), ["RenderDoc core/qrenderdoc/renderdoccmd markers found."]

    unity_score = sum(1 for item in ["Assets", "Packages", "ProjectSettings"] if top_dir_marker(inventory, item))
    unreal_score = 0
    for sample in inventory.get("sample_files", []):
        lower = sample.lower()
        if lower.endswith(".uproject") or lower.endswith(".uplugin") or lower.endswith(".build.cs"):
            unreal_score += 1

    engine_concepts = ["rhi", "render_graph", "gpu_marker", "shader", "material", "mesh", "pso"]
    engine_hits = sum(1 for name in engine_concepts if concepts.get(name, {}).get("status") == "found")
    engine_maybes = sum(1 for name in engine_concepts if concepts.get(name, {}).get("status") == "maybe")
    source_renderer_dirs = any(top_dir_marker(inventory, d) for d in ["Engine", "Renderer", "RHI", "Source"])

    if engine == "unity" or unity_score >= 3:
        if engine_hits >= 2:
            return "game_engine_repo", 0.78, ["Unity-style directories plus renderer/RHI concepts found."]
        return "unity_project", 0.8 if unity_score >= 3 else 0.55, ["Unity project directory markers found."]

    if engine == "unreal" or unreal_score > 0:
        if engine_hits >= 2:
            return "game_engine_repo", 0.82, ["Unreal markers plus engine renderer/RHI concepts found."]
        return "unreal_project_or_plugin", 0.75, ["Unreal project/plugin/build markers found."]

    if engine_hits >= 2 or (engine_hits >= 1 and engine_maybes >= 2) or (
        source_renderer_dirs and concepts.get("rhi", {}).get("status") == "found"
    ):
        return "game_engine_repo", min(0.92, 0.62 + 0.08 * engine_hits + 0.03 * engine_maybes), [
            "Renderer/RHI-style concepts found."
        ]

    if top_dir_marker(inventory, "Content") or top_dir_marker(inventory, "Assets") or top_dir_marker(inventory, "Scripts"):
        return "game_project_repo", 0.58, ["Game content/project markers found, but renderer/RHI concepts are weak."]

    return "unknown", 0.0, notes


def build_manifest(repo, scan, inventory, concepts, engine):
    repo_type, repo_confidence, notes = classify_repo(inventory, concepts, engine)

    repo_type_candidate = {
        "path": ".",
        "score": repo_confidence,
        "matched_keywords": [repo_type] if repo_type != "unknown" else [],
        "matched_patterns": [],
        "evidence_lines": [{"line": 0, "text": note} for note in notes[:10]],
        "reason": "; ".join(notes) if notes else "No strong repository type markers found.",
        "risk": "Low-confidence classification should be manually confirmed before implementation.",
        "recommended_eap_usage": "Use repository type only to choose the next reconnaissance or bridge task.",
    }
    concepts["repo_type"] = {
        "status": "found" if repo_type != "unknown" else "not_found",
        "confidence": repo_confidence,
        "candidates": [repo_type_candidate] if repo_type != "unknown" else [],
    }

    languages = sorted(inventory.get("languages", {}).keys())
    build_systems = sorted(inventory.get("build_systems", {}).keys())
    recommendation = make_recommendation(repo_type, repo_confidence, concepts)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repo": {
            "path": normalize_path(repo),
            "type": repo_type,
            "confidence": repo_confidence,
            "languages": languages,
            "build_systems": build_systems,
        },
        "scan": scan,
        "concepts": concepts,
        "recommendation": recommendation,
        "_inventory": inventory,
    }


def make_recommendation(repo_type, repo_confidence, concepts):
    notes = []
    wrong_repo = False
    task = "RepoReconOnly"

    if repo_type == "renderdoc_fork":
        wrong_repo = True
        task = "RepoReconOnly"
        notes.append("This is a RenderDoc fork/tool workspace; do not implement engine-side EAP emission here.")
    elif repo_confidence < 0.45:
        task = "RepoReconOnly"
        notes.append("Repository classification confidence is low; require human confirmation before code changes.")
    elif repo_type == "game_project_repo":
        task = "EngineModuleSelection"
        notes.append("Project content found, but renderer/RHI ownership is not clear.")
    elif repo_type in ("game_engine_repo", "unreal_project_or_plugin", "unity_project"):
        renderdoc_found = concepts.get("renderdoc_integration", {}).get("status") == "found"
        engine_hook_found = any(
            concepts.get(name, {}).get("status") == "found" for name in ["rhi", "render_graph", "gpu_marker"]
        )
        eap_core_found = any(
            "eap." in line.get("text", "").lower()
            for data in concepts.values()
            for cand in data.get("candidates", [])
            for line in cand.get("evidence_lines", [])
        )
        if renderdoc_found and not eap_core_found:
            task = "EAPCoreTypes"
            notes.append("RenderDoc integration exists, but EAP core types were not detected.")
        elif engine_hook_found:
            task = "RenderDocBridge MVP"
            notes.append("Engine/RHI/render graph hook candidates exist; RenderDocBridge MVP is the next useful task.")
        else:
            task = "EngineModuleSelection"
            notes.append("Engine-ish repository found, but hook ownership needs confirmation.")

    return {
        "is_wrong_repo_for_engine_emission": wrong_repo,
        "recommended_next_task": task,
        "prompt_file": "codex_next_prompt.md",
        "notes": notes,
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def manifest_for_output(manifest):
    data = dict(manifest)
    data.pop("_inventory", None)
    return data


def write_manifest(manifest, out_dir):
    write_json(Path(out_dir) / "eap_repo_manifest.json", manifest_for_output(manifest))


def concept_candidates(manifest, concept_name):
    return manifest.get("concepts", {}).get(concept_name, {}).get("candidates", [])


def top_paths(manifest, concept_names, limit=6):
    seen = set()
    rows = []
    for name in concept_names:
        for cand in concept_candidates(manifest, name):
            key = cand.get("path", "")
            if key and key not in seen:
                rows.append((name, cand))
                seen.add(key)
            if len(rows) >= limit:
                return rows
    return rows


def candidate_table(manifest, concept_names, empty_text="未发现"):
    rows = top_paths(manifest, concept_names, limit=12)
    if not rows:
        return empty_text
    lines = ["| Concept | Path | Score | Evidence | Recommended usage |", "| --- | --- | ---: | --- | --- |"]
    for concept, cand in rows:
        evidence = "; ".join([line.get("text", "") for line in cand.get("evidence_lines", [])[:2]])
        lines.append(
            "| {0} | `{1}` | {2:.2f} | {3} | {4} |".format(
                concept,
                cand.get("path", ""),
                float(cand.get("score", 0.0)),
                evidence.replace("|", "\\|"),
                cand.get("recommended_eap_usage", "").replace("|", "\\|"),
            )
        )
    return "\n".join(lines)


def status_line(manifest, concept):
    data = manifest.get("concepts", {}).get(concept, {})
    return "{0} ({1:.2f})".format(data.get("status", "not_found"), float(data.get("confidence", 0.0)))


def build_implementation_map_body(manifest):
    repo = manifest["repo"]
    scan = manifest["scan"]
    rec = manifest["recommendation"]
    languages = ", ".join(repo.get("languages", [])) or "未发现"
    build_systems = ", ".join(repo.get("build_systems", [])) or "未发现"

    lines = []
    lines.append("## 1. Repository Summary")
    lines.append("")
    lines.append("- Repository path: `{0}`".format(repo["path"]))
    lines.append("- Repository type: `{0}` (confidence {1:.2f})".format(repo["type"], repo["confidence"]))
    lines.append("- Languages: {0}".format(languages))
    lines.append("- Build systems: {0}".format(build_systems))
    lines.append("- Files seen/scanned/skipped: {0}/{1}/{2}".format(scan["files_seen"], scan["files_scanned"], scan["files_skipped"]))
    lines.append("- Recommendation: `{0}`".format(rec["recommended_next_task"]))
    if rec.get("is_wrong_repo_for_engine_emission"):
        lines.append("- EAP placement: this is the wrong repo for engine-side emission; use it as a tooling/reference repo only.")
    else:
        lines.append("- EAP placement: choose the engine diagnostics/rendering layer indicated by the candidates below.")
    lines.append("")

    lines.append("## 2. Existing RenderDoc Integration")
    lines.append("")
    lines.append(candidate_table(manifest, ["renderdoc_integration"], "未发现 RenderDoc integration candidates. Searched RenderDoc API/header/library keywords."))
    lines.append("")

    lines.append("## 3. Proposed EAP Module Layout")
    lines.append("")
    if repo["type"] == "renderdoc_fork":
        lines.append("- Do not place engine-side EAP runtime modules under `renderdoc/`, `qrenderdoc/`, or `renderdoccmd/`.")
        lines.append("- Keep this repo's EAP work under `tools/eap_scout/`, `Docs/EAP/`, and later optional analyzer consumers.")
    else:
        lines.append("- Recommended runtime/developer module candidates are derived from RHI/render graph/marker paths:")
        lines.append(candidate_table(manifest, ["rhi", "render_graph", "gpu_marker"], "未发现明确模块路径，先做 EngineModuleSelection。"))
    lines.append("")

    lines.append("## 4. RenderDocBridge Insertion Point")
    lines.append("")
    lines.append("- RenderDoc integration status: {0}".format(status_line(manifest, "renderdoc_integration")))
    lines.append("- RHI status: {0}".format(status_line(manifest, "rhi")))
    lines.append("- Recommended insertion evidence:")
    lines.append(candidate_table(manifest, ["renderdoc_integration", "rhi", "gpu_marker"], "未发现；下一轮应先人工确认 bridge owner module。"))
    lines.append("")

    lines.append("## 5. RenderGraph / Pass Hook Points")
    lines.append("")
    lines.append("- Render graph status: {0}".format(status_line(manifest, "render_graph")))
    lines.append(candidate_table(manifest, ["render_graph"], "未发现 render graph/pass candidates; searched RenderGraph/AddPass/ExecutePass/FrameGraph keywords."))
    lines.append("")

    lines.append("## 6. Draw / Dispatch Hook Points")
    lines.append("")
    lines.append("- Draw status: {0}".format(status_line(manifest, "draw")))
    lines.append("- Dispatch status: {0}".format(status_line(manifest, "dispatch")))
    lines.append(candidate_table(manifest, ["draw", "dispatch", "command_list", "command_buffer"], "未发现 draw/dispatch candidates."))
    lines.append("")

    lines.append("## 7. Resource Annotation Hook Points")
    lines.append("")
    lines.append(candidate_table(manifest, ["texture", "buffer", "asset", "streaming"], "未发现 resource/asset/streaming candidates."))
    lines.append("")

    lines.append("## 8. Sidecar Metadata Output Point")
    lines.append("")
    lines.append("- Capture/config candidates:")
    lines.append(candidate_table(manifest, ["renderdoc_integration", "config", "console_variable"], "未发现 capture/config candidates; use engine frame end/capture end once identified."))
    lines.append("- MVP policy: write only local reports now; do not implement sidecar writer in this scout task.")
    lines.append("")

    lines.append("## 9. Feature Flag / Runtime Toggle")
    lines.append("")
    lines.append(candidate_table(manifest, ["config", "console_variable"], "未发现 config/CVar candidates. Suggested names remain `ENABLE_EAP`, `eap.enabled`, `eap.emit_annotations`, `eap.emit_sidecar`, `eap.capture_only`."))
    lines.append("")

    lines.append("## 10. Build System Changes Needed Later")
    lines.append("")
    lines.append(candidate_table(manifest, ["build_system"], "未发现 build-system candidates."))
    lines.append("- Later changes must be limited to the selected engine/tool module, not RenderDoc core.")
    lines.append("")

    lines.append("## 11. Test Plan")
    lines.append("")
    lines.append(candidate_table(manifest, ["tests"], "未发现 tests candidates; add bridge/core unit tests in the selected module later."))
    lines.append("- Required future cases: RenderDoc absent, API too old, sidecar write success/failure, annotation budget, multithreaded command recording, Windows/Linux/Android differences.")
    lines.append("")

    lines.append("## 12. Risk Register")
    lines.append("")
    risk_rows = [
        ("Wrong repo/module ownership", "Bridge lands in tooling or content repo instead of engine renderer/diagnostics.", rec["recommended_next_task"] == "EngineModuleSelection"),
        ("RenderDoc absent", "Bridge must no-op without RenderDoc installed or injected.", False),
        ("API version too old", "Annotations require API 1.7.0.", False),
        ("Hot-path overhead", "Draw/dispatch scanning must be capture-only and budgeted.", True),
        ("Threaded command recording", "Annotations must be emitted on valid command-list ownership thread.", True),
        ("Resource lifetime/aliasing", "Object annotations may outlive transient resources.", True),
        ("Asset path leakage", "Sidecar/annotations can expose project paths.", False),
        ("Shipping leakage", "EAP must be disabled in shipping builds.", True),
        ("Android remote capture paths", "RDC and sidecar may be produced on different machines.", False),
        ("Backend differences", "D3D12/Vulkan queue/command-buffer behavior differs from D3D11/GL.", True),
    ]
    lines.append("| Risk | Impact | MVP blocker |")
    lines.append("| --- | --- | ---: |")
    for risk, impact, blocker in risk_rows:
        lines.append("| {0} | {1} | {2} |".format(risk, impact, "yes" if blocker else "no"))
    lines.append("")

    lines.append("## 13. Proposed Next Codex Task")
    lines.append("")
    lines.append("- Task name: {0}".format(rec["recommended_next_task"]))
    lines.append("- Goal: {0}".format(next_task_goal(repo["type"], rec["recommended_next_task"])))
    lines.append("- Files to modify: selected by the next task from the candidate paths above.")
    lines.append("- Files to add: no runtime files should be added by EAP Scout; next implementation should add only bridge/core files in the selected engine module.")
    lines.append("- Exact acceptance criteria: keep RenderDoc core untouched, keep scanned repo untouched during scout, and require tests before runtime work.")
    lines.append("- Commands to build/test: use the target repo's focused test/build commands after module ownership is confirmed.")
    lines.append("- Rollback plan: delete only the new EAP module files and build references from the target engine repo.")
    lines.append("")
    return "\n".join(lines)


def next_task_goal(repo_type, task):
    if repo_type == "renderdoc_fork":
        return "Stop before engine-side emission and scan the real game/engine repository."
    if task == "RenderDocBridge MVP":
        return "Implement a no-op-safe dynamic RenderDoc app API bridge in the selected engine diagnostics module."
    if task == "EngineModuleSelection":
        return "Manually confirm the engine module that owns rendering/RHI diagnostics before writing code."
    if task == "EAPCoreTypes":
        return "Add EAP typed keys/values and validation around an existing RenderDoc bridge."
    return "Continue read-only reconnaissance."


def build_hook_candidates_body(manifest):
    groups = [
        ("RenderDoc Integration", ["renderdoc_integration"]),
        ("RHI / Command List", ["rhi", "command_list", "command_buffer"]),
        ("RenderGraph / Pass", ["render_graph"]),
        ("Draw / Dispatch", ["draw", "dispatch"]),
        ("Resource", ["texture", "buffer", "asset", "streaming"]),
        ("Material / Shader / Mesh / PSO", ["material", "shader", "mesh", "pso"]),
        ("Config / CVar", ["config", "console_variable"]),
        ("Tests", ["tests"]),
    ]
    lines = []
    for title, concepts in groups:
        lines.append("## " + title)
        lines.append("")
        lines.append(candidate_table(manifest, concepts, "未发现"))
        lines.append("")
    return "\n".join(lines)


def read_template(name, fallback):
    path = TOOL_ROOT / "templates" / name
    if path.exists():
        try:
            with open(str(path), "r", encoding="utf-8") as handle:
                return handle.read()
        except IOError:
            pass
    return fallback


def render_template(name, body, manifest=None):
    if name == "EAP_IMPLEMENTATION_MAP.md.tmpl":
        title = "EAP Implementation Map"
    elif name == "EAP_HOOK_CANDIDATES.md.tmpl":
        title = "EAP Hook Candidates"
    else:
        title = "Codex Next Prompt"
    fallback = "# " + title + "\n\n{{body}}\n"
    template = read_template(name, fallback)
    text = template.replace("{{body}}", body)
    if manifest:
        text = text.replace("{{repo_type}}", manifest["repo"]["type"])
        text = text.replace("{{recommended_next_task}}", manifest["recommendation"]["recommended_next_task"])
    return text.rstrip() + "\n"


def write_markdown_reports(manifest, out_dir):
    out = Path(out_dir)
    impl = render_template("EAP_IMPLEMENTATION_MAP.md.tmpl", build_implementation_map_body(manifest), manifest)
    hooks = render_template("EAP_HOOK_CANDIDATES.md.tmpl", build_hook_candidates_body(manifest), manifest)
    (out / "EAP_IMPLEMENTATION_MAP.md").write_text(impl, encoding="utf-8")
    (out / "EAP_HOOK_CANDIDATES.md").write_text(hooks, encoding="utf-8")


def recommended_dirs_for_prompt(manifest):
    rows = top_paths(manifest, ["rhi", "render_graph", "gpu_marker", "build_system"], limit=8)
    dirs = []
    for _concept, cand in rows:
        parent = normalize_path(Path(cand.get("path", "")).parent)
        if parent and parent != "." and parent not in dirs:
            dirs.append(parent)
    return dirs


def build_prompt_body(manifest, task):
    repo = manifest["repo"]
    rec = manifest["recommendation"]
    low_confidence = repo.get("confidence", 0.0) < 0.55
    lines = []
    lines.append("You are a C++ / Python tooling / RenderDoc / game-engine tooling agent.")
    lines.append("")
    lines.append("Repository scanned by EAP Scout:")
    lines.append("- Path: `{0}`".format(repo["path"]))
    lines.append("- Type: `{0}` (confidence {1:.2f})".format(repo["type"], repo["confidence"]))
    lines.append("- Recommended next task: `{0}`".format(rec["recommended_next_task"]))
    lines.append("")

    if repo["type"] == "renderdoc_fork":
        lines.append("This is a RenderDoc fork/tooling repository. Do not implement engine-side bridge or EAP emission here.")
        lines.append("Allowed next work is read-only reconnaissance, scanner/report tooling, or analyzer-side consumers only.")
    elif low_confidence:
        lines.append("Classification confidence is low. First manually confirm repository/module ownership.")
        lines.append("Do not write runtime code until the owner module is confirmed by a human.")
    else:
        lines.append("Recommended implementation directories to inspect first:")
        dirs = recommended_dirs_for_prompt(manifest)
        if dirs:
            for item in dirs:
                lines.append("- `{0}`".format(item))
        else:
            lines.append("- 未发现明确目录；先做 EngineModuleSelection。")
        lines.append("")
        lines.append("Forbidden directories/actions for the next implementation:")
        lines.append("- Do not modify RenderDoc core.")
        lines.append("- Do not modify third-party/vendor directories.")
        lines.append("- Do not modify shader code or resource loading unless explicitly approved.")
        lines.append("- Do not introduce third-party dependencies.")

    lines.append("")
    lines.append("Evidence highlights:")
    for concept in ["renderdoc_integration", "rhi", "render_graph", "gpu_marker", "build_system", "tests"]:
        lines.append("- {0}: {1}".format(concept, status_line(manifest, concept)))

    lines.append("")
    lines.append("Task request:")
    if rec["recommended_next_task"] == "RenderDocBridge MVP":
        lines.append("Implement a minimal no-op-safe RenderDoc app API bridge in the selected engine diagnostics module.")
    elif rec["recommended_next_task"] == "EAPCoreTypes":
        lines.append("Add EAP key/value core types and validation around the existing RenderDoc bridge.")
    elif rec["recommended_next_task"] == "EngineModuleSelection":
        lines.append("Perform read-only module ownership confirmation and produce a smaller implementation plan.")
    else:
        lines.append("Continue read-only reconnaissance; do not implement engine-side emission.")
    lines.append("")
    lines.append("Use the generated `EAP_IMPLEMENTATION_MAP.md`, `EAP_HOOK_CANDIDATES.md`, and evidence JSON files as input.")
    return "\n".join(lines)


def write_codex_prompt(manifest, out_path, task="renderdoc_bridge"):
    prompt = render_template("codex_next_prompt.md.tmpl", build_prompt_body(manifest, task), manifest)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding="utf-8")


def output_file(path, default_name):
    out = Path(path)
    if out.suffix:
        return out
    return out / default_name


def write_evidence(manifest, out_dir):
    evidence = Path(out_dir) / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    inventory = manifest.get("_inventory", {})
    write_json(evidence / "repo_inventory.json", {
        "repo": manifest["repo"],
        "scan": manifest["scan"],
        "inventory": inventory,
        "repo_type": manifest["concepts"].get("repo_type", {}),
    })
    for filename, concepts in EVIDENCE_FILES.items():
        if filename == "repo_inventory.json":
            continue
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": manifest["generated_at"],
            "concepts": {
                name: manifest["concepts"].get(name, {"status": "not_found", "confidence": 0.0, "candidates": []})
                for name in concepts
            },
        }
        write_json(evidence / filename, payload)


def run_scan(repo, out, engine="auto", max_files=DEFAULT_MAX_FILES):
    manifest = scan_repo(repo, max_files=max_files, engine=engine)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, out_dir)
    write_markdown_reports(manifest, out_dir)
    write_codex_prompt(manifest, out_dir / "codex_next_prompt.md", task="renderdoc_bridge")
    write_evidence(manifest, out_dir)
    return manifest


def run_prompt(manifest_path, task, out):
    manifest = read_json_file(Path(manifest_path))
    out_path = output_file(out, "codex_next_prompt.md")
    write_codex_prompt(manifest, out_path, task=task)
    return out_path


def run_summarize(reports, out):
    reports_dir = Path(reports)
    manifests = []
    for path in sorted(reports_dir.rglob("eap_repo_manifest.json")):
        try:
            manifests.append(read_json_file(path))
        except (IOError, ValueError):
            continue
    summary = {
        "schema_version": "eap_scout_summary.v1",
        "generated_at": utc_now(),
        "report_count": len(manifests),
        "repositories": [
            {
                "path": item.get("repo", {}).get("path", ""),
                "type": item.get("repo", {}).get("type", "unknown"),
                "confidence": item.get("repo", {}).get("confidence", 0.0),
                "recommended_next_task": item.get("recommendation", {}).get("recommended_next_task", "RepoReconOnly"),
            }
            for item in manifests
        ],
    }
    out_path = output_file(out, "eap_scout_summary.json")
    write_json(out_path, summary)
    return out_path


def main(argv=None):
    args = parse_args(argv)
    if args.command == "scan":
        manifest = run_scan(args.repo, args.out, engine=args.engine, max_files=args.max_files)
        print("EAP Scout scan complete: {0}".format(Path(args.out) / "eap_repo_manifest.json"))
        print("repo_type={0} next_task={1}".format(
            manifest["repo"]["type"], manifest["recommendation"]["recommended_next_task"]
        ))
        return 0
    if args.command == "prompt":
        path = run_prompt(args.manifest, args.task, args.out)
        print("EAP Scout prompt written: {0}".format(path))
        return 0
    if args.command == "summarize":
        path = run_summarize(args.reports, args.out)
        print("EAP Scout summary written: {0}".format(path))
        return 0
    print("No command specified. Use --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
