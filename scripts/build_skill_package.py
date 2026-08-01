#!/usr/bin/env python3
"""Build a deterministic runtime archive without repository-only files."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
INCLUDED = (
    "SKILL.md",
    "agents/openai.yaml",
    "references",
    "schemas",
    "scripts/adapter_runtime.py",
    "scripts/configuration_run.py",
    "scripts/diff_object_graph.py",
    "scripts/validate_configuration_contract.py",
    "scripts/validate_contract_conformance.py",
    "LICENSE",
)


def package_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDED:
        source = ROOT / name
        if source.is_file():
            files.append(source)
        elif source.is_dir():
            files.extend(
                path
                for path in source.rglob("*")
                if path.is_file() and path.suffix in {".md", ".json"}
            )
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in package_files():
            relative = Path("configure-gtm") / path.relative_to(ROOT)
            info = ZipInfo(relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
    print(f"Created {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
