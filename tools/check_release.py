#!/usr/bin/env python3
"""Check the current skill structure, schemas, release metadata and archive."""

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

from build_skill_package import build, package_files
from check_architecture import inspect_architecture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure_gtm import COMMANDS
from gtm_configure.core.model import CONTRACT_SCHEMA_VERSION, SCHEMA_VERSION
from gtm_configure.core.schemas import validator

CURRENT_RELEASE = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SEMVER = re.compile(r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
LINK = re.compile(r"\]\(([^)]+)\)")
MANDATORY_CORE = (
    "SKILL.md",
    "references/core/authority.md",
    "references/core/workflow.md",
    "references/core/authoring.md",
    "references/core/execution.md",
    "references/core/acceptance.md",
)


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def assigned_string_constant(source, name):
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    return None


def check_files_and_routing():
    errors = []
    references = set((ROOT / "references").rglob("*.md"))
    visited = set()
    pending = [ROOT / "SKILL.md"]
    while pending:
        source = pending.pop().resolve()
        if source in visited:
            continue
        visited.add(source)
        for label, link in re.findall(
            r"\[([^\]]+)\]\(([^)]+)\)", source.read_text(encoding="utf-8")
        ):
            if re.fullmatch(r"[\w./-]+\.md(?:#[\w-]+)?", label) and "://" not in link:
                if Path(label.split("#")[0]).name != Path(link.split("#")[0]).name:
                    errors.append(f"{source.name}: file label {label} differs from {link}")
        for link in LINK.findall(source.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("mailto:"):
                continue
            filename, _, anchor = link.partition("#")
            target = (source.parent / filename).resolve() if filename else source
            if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                errors.append(f"{source.name}: missing or escaping resource {link}")
                continue
            if target.suffix == ".md":
                pending.append(target)
                if anchor:
                    anchors = {
                        re.sub(r"[^\w -]", "", h.strip().casefold()).replace(" ", "-")
                        for h in re.findall(
                            r"^#{1,6} +(.+)$", target.read_text(encoding="utf-8"), re.M
                        )
                    }
                    if anchor not in anchors:
                        errors.append(f"{source.name}: missing anchor {link}")
    errors.extend(
        f"unrouted reference: {p.relative_to(ROOT)}" for p in sorted(references - visited)
    )
    return errors


def check_versions_and_schemas():
    errors = []
    metadata = tomllib.loads(read("pyproject.toml"))
    if metadata["project"]["version"] != CURRENT_RELEASE:
        errors.append("pyproject version differs from VERSION")
    if f"v{CURRENT_RELEASE}" not in read("README.md"):
        errors.append("README is missing current version")
    versions = {"contract": CONTRACT_SCHEMA_VERSION, "run": SCHEMA_VERSION}
    for kind, version in versions.items():
        v = validator(kind)
        v.check_schema(v.schema)
        if v.schema["properties"]["schema_version"]["const"] != version:
            errors.append(f"wrong {kind} schema version")
        errors.extend(
            schema_version_claim_errors(v.schema.get("title", ""), versions, f"{kind} schema title")
        )
    for path in [ROOT / "SKILL.md", *sorted((ROOT / "references").rglob("*.md"))]:
        errors.extend(
            schema_version_claim_errors(
                path.read_text(encoding="utf-8"), versions, str(path.relative_to(ROOT))
            )
        )
    for path in (ROOT / "scripts").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                errors.extend(
                    schema_version_claim_errors(
                        ast.get_docstring(node) or "",
                        versions,
                        f"{path.relative_to(ROOT)} docstring",
                    )
                )
    return errors


def schema_version_claim_errors(source, versions, locator):
    """Current executable/instruction claims refer to their schema owner's version."""
    return [
        f"{locator}: stale {kind}@{version}; current schema is {versions[kind]}"
        for kind, version in re.findall(
            r"(?:configuration-)?(contract|run)@(\d+(?:\.\d+)+)", source
        )
        if versions[kind] != version
    ]


def check_runtime_package():
    errors = []
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "skill.zip"
        build(output)
        with ZipFile(output) as archive:
            for path in package_files():
                name = "configure-gtm/" + path.relative_to(ROOT).as_posix()
                if archive.read(name) != path.read_bytes():
                    errors.append(f"archive byte mismatch: {name}")
            archive.extractall(directory)
        script = Path(directory) / "configure-gtm/scripts/configure_gtm.py"
        for command in COMMANDS:
            result = subprocess.run(
                [sys.executable, "-B", str(script), command, "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode:
                errors.append(f"packaged {command}: {result.stderr}")
            elif f"configure_gtm.py {command}" not in result.stdout:
                errors.append(f"packaged {command}: help usage omits its command")
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
        if result.returncode != 0:
            errors.append(f"could not verify HEAD tags: git exited {result.returncode}")
        elif tag not in result.stdout.splitlines():
            errors.append(f"HEAD is not tagged {tag}")
    if require_clean:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"could not verify working tree: git exited {result.returncode}")
        elif result.stdout.strip():
            errors.append("working tree is not clean")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--release-notes", type=Path, default=ROOT / "CHANGELOG.md")
    parser.add_argument("--require-git-tag", action="store_true")
    parser.add_argument("--require-clean-tree", action="store_true")
    args = parser.parse_args()
    errors = check_files_and_routing() + check_versions_and_schemas() + check_runtime_package()
    errors += inspect_architecture()[1]
    errors += check_git_state(
        tag=args.tag, require_tag=args.require_git_tag, require_clean=args.require_clean_tree
    )
    errors += check_release_notes(args.release_notes)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Release check: {'FAIL' if errors else 'PASS'} (v{CURRENT_RELEASE})")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
