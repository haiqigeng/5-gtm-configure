#!/usr/bin/env python3
"""Validate configure-gtm repository, routed runtime, and release coherence."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from zipfile import ZipFile

from build_skill_package import INCLUDED, build, package_files
from strict_json import StrictJsonError, loads_strict

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE = "9.0.0"
SEMVER = re.compile(r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
LINK = re.compile(r"\]\(([^)]+)\)")
WORD = re.compile(r"\b[\w-]+\b")
V8_MANDATORY_CORE_WORDS = 7214

REFERENCE_FILES = {
    "references/01-orientation/official-source-policy.md",
    "references/01-orientation/utility-contract.md",
    "references/02-execution/analytics-tags.md",
    "references/02-execution/analytics-vendors.md",
    "references/02-execution/client-side-object-surface.md",
    "references/02-execution/cmp-consent.md",
    "references/02-execution/cmp-platform-patterns.md",
    "references/02-execution/configuration-contract.md",
    "references/02-execution/configuration-run-and-resume.md",
    "references/02-execution/conversion-linker-cross-domain.md",
    "references/02-execution/data-contract-and-transformations.md",
    "references/02-execution/first-party-data.md",
    "references/02-execution/ga4-collection-safety.md",
    "references/02-execution/google-consent-mode.md",
    "references/02-execution/google-field-ownership.md",
    "references/02-execution/implementation-workflow.md",
    "references/02-execution/media-affiliate.md",
    "references/02-execution/media-criteo.md",
    "references/02-execution/media-floodlight.md",
    "references/02-execution/media-google-ads.md",
    "references/02-execution/media-linkedin.md",
    "references/02-execution/media-meta.md",
    "references/02-execution/media-microsoft-ads.md",
    "references/02-execution/media-pinterest.md",
    "references/02-execution/media-reddit.md",
    "references/02-execution/media-snapchat.md",
    "references/02-execution/media-tags.md",
    "references/02-execution/media-tiktok.md",
    "references/02-execution/media-x.md",
    "references/02-execution/multi-destination-routing.md",
    "references/02-execution/naming-and-reuse.md",
    "references/02-execution/pipeline/architecture-and-workflow.md",
    "references/02-execution/pipeline/browser-server-deduplication.md",
    "references/02-execution/pipeline/transport-data-contract.md",
    "references/02-execution/server/analytics-ga4.md",
    "references/02-execution/server/analytics-vendors.md",
    "references/02-execution/server/consent-and-data-governance.md",
    "references/02-execution/server/first-party-data-and-secrets.md",
    "references/02-execution/server/media-affiliate.md",
    "references/02-execution/server/media-criteo.md",
    "references/02-execution/server/media-destinations.md",
    "references/02-execution/server/media-floodlight.md",
    "references/02-execution/server/media-google-ads.md",
    "references/02-execution/server/media-linkedin.md",
    "references/02-execution/server/media-meta.md",
    "references/02-execution/server/media-microsoft-ads.md",
    "references/02-execution/server/media-pinterest.md",
    "references/02-execution/server/media-reddit.md",
    "references/02-execution/server/media-snapchat.md",
    "references/02-execution/server/media-tiktok.md",
    "references/02-execution/server/media-x.md",
    "references/02-execution/server/object-surface-and-ingress.md",
    "references/02-execution/server/tags-triggers-and-variables.md",
    "references/02-execution/server/transformations.md",
    "references/02-execution/tcf-consent.md",
    "references/02-execution/template-governance.md",
    "references/02-execution/tool-adapters.md",
    "references/02-execution/tracking-plan-fidelity-and-conformance.md",
    "references/02-execution/tracking-refonte.md",
    "references/02-execution/transformation-patterns.md",
    "references/02-execution/triggers-and-variables.md",
    "references/02-execution/vendor-consent-modes.md",
    "references/03-judgement/acceptance-and-handoff.md",
}
ALLOWED_REFERENCE_DIRS = {
    "references/01-orientation",
    "references/02-execution",
    "references/02-execution/pipeline",
    "references/02-execution/server",
    "references/03-judgement",
}
REQUIRED_REPOSITORY_FILES = {
    "VERSION",
    "SKILL.md",
    "agents/openai.yaml",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "pyproject.toml",
    ".gitattributes",
    ".gitignore",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "scripts/check_release.py",
    "scripts/build_skill_package.py",
    "tests/test_v9_contract_and_run.py",
    "tests/test_v9_adapter_runtime.py",
    "tests/test_v9_documentation.py",
    "tests/fixtures/server_pipeline_scenarios.json",
} | REFERENCE_FILES
SCAN_EXCLUDED = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "venv",
}
MANDATORY_CORE = (
    "SKILL.md",
    "references/01-orientation/utility-contract.md",
    "references/02-execution/implementation-workflow.md",
    "references/02-execution/configuration-contract.md",
    "references/02-execution/configuration-run-and-resume.md",
    "references/03-judgement/acceptance-and-handoff.md",
)
MEDIA_NAMES = (
    "affiliate",
    "criteo",
    "floodlight",
    "google-ads",
    "linkedin",
    "meta",
    "microsoft-ads",
    "pinterest",
    "reddit",
    "snapchat",
    "tiktok",
    "x",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def assigned_string_constant(source: str, name: str) -> str | None:
    """Return one exact top-level string assignment without substring matching."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _reference_inventory() -> set[str]:
    return {path.relative_to(ROOT).as_posix() for path in (ROOT / "references").rglob("*.md")}


def check_files_and_routing() -> list[str]:
    errors = [
        f"missing required file: {relative}"
        for relative in sorted(REQUIRED_REPOSITORY_FILES)
        if not (ROOT / relative).is_file()
    ]
    actual_references = _reference_inventory()
    for relative in sorted(REFERENCE_FILES - actual_references):
        errors.append(f"missing reference: {relative}")
    for relative in sorted(actual_references - REFERENCE_FILES):
        errors.append(f"unexpected reference: {relative}")
    actual_dirs = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "references").rglob("*")
        if path.is_dir()
    }
    for relative in sorted(actual_dirs - ALLOWED_REFERENCE_DIRS):
        errors.append(f"unexpected reference directory: {relative}")

    skill = read("SKILL.md")
    links = {value for value in LINK.findall(skill) if value.startswith("references/")}
    for relative in sorted(actual_references - links):
        errors.append(f"reference is not directly routed from SKILL.md: {relative}")
    for relative in sorted(links - actual_references):
        errors.append(f"SKILL.md routes a missing reference: {relative}")
    for link in LINK.findall(skill):
        if not link.startswith(("http://", "https://")) and not (ROOT / link).exists():
            errors.append(f"SKILL.md references missing resource: {link}")

    headings = ["## 01 - Orientation", "## 02 - Execution", "## 03 - Judgement"]
    positions = [skill.find(heading) for heading in headings]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("SKILL.md must route orientation, execution, then judgement")
    for relative in sorted(actual_references):
        text = read(relative)
        if len(text.splitlines()) > 100 and "## Contents" not in text:
            errors.append(f"long reference is missing a Contents section: {relative}")
    return errors


def check_versions_and_schemas() -> list[str]:
    errors: list[str] = []
    version = read("VERSION").strip()
    if version != CURRENT_RELEASE:
        errors.append(f"VERSION must be {CURRENT_RELEASE}, got {version!r}")
    metadata = tomllib.loads(read("pyproject.toml"))
    if metadata.get("project", {}).get("version") != CURRENT_RELEASE:
        errors.append("pyproject.toml version does not match current release")
    for relative in (
        "README.md",
        "CHANGELOG.md",
        "agents/openai.yaml",
        "CONTRIBUTING.md",
        ".github/workflows/ci.yml",
    ):
        if CURRENT_RELEASE not in read(relative):
            errors.append(f"{relative} does not name current release {CURRENT_RELEASE}")

    model = read("scripts/run_model.py")
    expected = {
        "SCHEMA_VERSION": "3.0",
        "CONTRACT_SCHEMA_VERSION": "6.0",
    }
    for name, value in expected.items():
        actual = assigned_string_constant(model, name)
        if actual != value:
            errors.append(f"run_model.{name} must be {value!r}, got {actual!r}")
    if assigned_string_constant(read("scripts/run_model_web.py"), "SCHEMA_VERSION") != "2.1":
        errors.append("preserved web run model must remain schema 2.1")
    for relative in (
        "schemas/configuration-contract.schema.json",
        "schemas/configuration-run.schema.json",
        "schemas/configuration-run-2.1.schema.json",
        "tests/fixtures/server_pipeline_scenarios.json",
    ):
        try:
            loads_strict(read(relative), source=relative)
        except StrictJsonError as exc:
            errors.append(str(exc))
    return errors


def check_runtime_content() -> list[str]:
    errors: list[str] = []
    skill = read("SKILL.md")
    required_phrases = (
        "saved, verified GTM object graph",
        "Operationally implement an approved analytics tracking plan",
        "explicit media implementation brief",
        "web authority does not grant server authority",
        "receiver graph before changing a live sender endpoint",
        "incoming Google-native consent",
        "`items` is an array and `user_data` is an object",
        "GTM event-scoped CJS fallback",
        "Never publish",
    )
    folded = skill.casefold()
    for phrase in required_phrases:
        if phrase.casefold() not in folded:
            errors.append(f"SKILL.md missing v9 contract phrase: {phrase}")
    forbidden = (
        "server-side GTM, Conversions API, and browser/server deduplication remain future",
        "the skill performs client-side GTM configuration only",
    )
    combined = "\n".join(
        read(relative)
        for relative in (
            "SKILL.md",
            "README.md",
            "references/01-orientation/utility-contract.md",
        )
    ).casefold()
    for phrase in forbidden:
        if phrase.casefold() in combined:
            errors.append(f"stale client-only boundary remains: {phrase}")

    for name in MEDIA_NAMES:
        browser = read(f"references/02-execution/media-{name}.md")
        server = read(f"references/02-execution/server/media-{name}.md")
        if "## Server route" not in browser:
            errors.append(f"browser media-{name}.md lacks a concise server-route pointer")
        pointer = browser.rsplit("## Server route", 1)[-1]
        if len(WORD.findall(pointer)) > 90:
            errors.append(f"browser media-{name}.md duplicates excessive server detail")
        if "official" not in server.casefold() or "fail closed" not in server.casefold():
            errors.append(f"server media-{name}.md lacks official-source and fail-closed guidance")
    return errors


def check_runtime_package() -> list[str]:
    errors: list[str] = []
    for relative in INCLUDED:
        if not (ROOT / relative).exists():
            errors.append(f"runtime package input is missing: {relative}")
    packaged = {path.relative_to(ROOT).as_posix() for path in package_files()}
    required_modules = {
        "scripts/action_contract.py",
        "scripts/adapter_runtime.py",
        "scripts/adapter_runtime_web.py",
        "scripts/configuration_run.py",
        "scripts/redaction.py",
        "scripts/resource_registry.py",
        "scripts/run_model.py",
        "scripts/run_model_web.py",
        "scripts/run_render.py",
        "scripts/run_state.py",
        "scripts/run_validation_core.py",
        "scripts/run_validation_pipeline.py",
        "scripts/run_validation_server.py",
        "scripts/run_validation_web.py",
        "scripts/validate_configuration_contract.py",
        "scripts/validate_configuration_contract_v5.py",
        "scripts/verification.py",
        "scripts/web_domain_validation.py",
    }
    for relative in sorted(required_modules - packaged):
        errors.append(f"runtime package omits imported module: {relative}")
    if errors:
        return errors
    try:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "configure-gtm-runtime.zip"
            build(archive_path)
            with ZipFile(archive_path) as archive:
                archive.extractall(temporary)
            scripts_path = Path(temporary) / "configure-gtm" / "scripts"
            modules = sorted(Path(relative).stem for relative in required_modules)
            smoke = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import importlib,sys;sys.path.insert(0,sys.argv[1]);"
                        "[importlib.import_module(name) for name in sys.argv[2:]]"
                    ),
                    str(scripts_path),
                    *modules,
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
            )
            if smoke.returncode != 0:
                detail = (smoke.stderr or smoke.stdout).strip().splitlines()
                errors.append(
                    "clean runtime package import smoke failed: "
                    + (detail[-1] if detail else f"exit {smoke.returncode}")
                )
    except (OSError, ValueError) as exc:
        errors.append(f"clean runtime package import smoke could not run: {exc}")
    return errors


def check_generated_artifacts() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in SCAN_EXCLUDED for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            errors.append(f"generated bytecode must be removed: {relative}")
    return errors


def _current_release_section(path: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = f"## {CURRENT_RELEASE}"
    if heading not in lines:
        return None, [f"release notes missing current heading: {heading}"]
    start = lines.index(heading)
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end]), errors


def check_release_notes(path: Path) -> list[str]:
    section, errors = _current_release_section(path)
    if section is None:
        return errors
    for heading in (
        "### Why This Release Matters",
        "### What Changed",
        "### What Users Should Do",
        "### Validation",
        "### Known Limits",
    ):
        if heading not in section:
            errors.append(f"release notes missing heading: {heading.removeprefix('### ')}")
    if section.count(f"## {CURRENT_RELEASE}") != 1:
        errors.append("current release section is duplicated")
    return errors


def check_git_state(*, tag: str | None, require_tag: bool, require_clean: bool) -> list[str]:
    errors: list[str] = []
    if tag is not None:
        if not SEMVER.fullmatch(tag):
            errors.append(f"invalid Semantic Version release tag: {tag}")
        elif tag != f"v{CURRENT_RELEASE}":
            errors.append(f"release tag {tag} does not match current release v{CURRENT_RELEASE}")
    if require_tag and tag is None:
        errors.append("--require-git-tag requires --tag")
    if require_tag and tag is not None:
        result = subprocess.run(
            ["git", "tag", "--points-at", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if tag not in result.stdout.splitlines():
            errors.append(f"HEAD is not tagged {tag}")
    if require_clean:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            errors.append("working tree is not clean")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--release-notes", type=Path)
    parser.add_argument("--require-git-tag", action="store_true")
    parser.add_argument("--require-clean-tree", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    errors.extend(check_files_and_routing())
    errors.extend(check_versions_and_schemas())
    errors.extend(check_runtime_content())
    errors.extend(check_runtime_package())
    errors.extend(check_generated_artifacts())
    errors.extend(
        check_git_state(
            tag=args.tag,
            require_tag=args.require_git_tag,
            require_clean=args.require_clean_tree,
        )
    )
    if args.release_notes:
        errors.extend(check_release_notes(args.release_notes))

    if errors:
        print(f"Release check: FAIL ({len(errors)} error(s))", file=sys.stderr)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    core_words = sum(len(WORD.findall(read(relative))) for relative in MANDATORY_CORE)
    print(
        "Release check: PASS "
        f"(v{CURRENT_RELEASE}, {len(REFERENCE_FILES)} routed references, "
        f"mandatory core {core_words} words; v8 baseline {V8_MANDATORY_CORE_WORDS})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
