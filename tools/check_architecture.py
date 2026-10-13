"""Derive file ownership and enforce executable dependency boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module_index(root):
    return {
        ".".join(path.relative_to(root / "scripts").with_suffix("").parts): path
        for path in (root / "scripts/gtm_configure").rglob("*.py")
    }


def inspect_architecture(root=ROOT):
    modules = module_index(root)
    errors, records = [], {}
    constants, bodies = defaultdict(list), defaultdict(list)
    referenced = set()
    for directory in ("scripts", "tests", "tools"):
        for path in (root / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    referenced.add(node.id)
                elif isinstance(node, ast.Attribute):
                    referenced.add(node.attr)
                elif isinstance(node, ast.ImportFrom):
                    referenced.update(alias.name for alias in node.names)
    for module, path in sorted(modules.items()):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports, aliases = set(), {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in modules:
                        imports.add(alias.name)
                        aliases[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in modules:
                    imports.add(node.module)
                    for alias in node.names:
                        if alias.name.startswith("_"):
                            errors.append(f"{module}: private import {node.module}.{alias.name}")
                for alias in node.names:
                    imported = node.module + "." + alias.name
                    if imported in modules:
                        imports.add(imported)
                        aliases[alias.asname or alias.name] = imported
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and node.attr.startswith("_")
            ):
                errors.append(f"{module}: private access {aliases[node.value.id]}.{node.attr}")
        layer = module.split(".")[1]
        allowed = {"core": {"core"}, "domain": {"domain", "core"}}
        for imported in imports:
            if layer in allowed and imported.split(".")[1] not in allowed[layer]:
                errors.append(f"{module}: inverted dependency on {imported}")
        definitions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name != "main" and node.name not in referenced:
                    errors.append(f"unreferenced definition {module}.{node.name}")
                definitions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "lines": node.end_lineno - node.lineno + 1,
                    }
                )
                if isinstance(node, ast.FunctionDef):
                    body = [
                        n
                        for n in node.body
                        if not (
                            isinstance(n, ast.Expr)
                            and isinstance(n.value, ast.Constant)
                            and isinstance(n.value.value, str)
                        )
                    ]
                    fingerprint = ast.dump(ast.Module(body=body, type_ignores=[]))
                    # Empty stubs and single forwarding expressions carry no independent rule.
                    if len(fingerprint) > 180:
                        bodies[fingerprint].append(f"{module}.{node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        try:
                            ast.literal_eval(node.value)
                        except (ValueError, TypeError):
                            continue
                        constants[target.id].append(module)
                        if target.id not in referenced:
                            errors.append(f"unreferenced constant {module}.{target.id}")
        records[module] = {
            "path": path.relative_to(root).as_posix(),
            "imports": sorted(imports),
            "definitions": definitions,
        }
    for name, owners in constants.items():
        if len(owners) > 1:
            errors.append(f"duplicate constant owner {name}: {', '.join(owners)}")
    for owners in bodies.values():
        if len(owners) > 1:
            errors.append(f"duplicate function implementation: {', '.join(owners)}")
    visited, visiting = set(), set()

    def walk(module):
        if module in visiting:
            errors.append(f"dependency cycle at {module}")
            return
        if module in visited:
            return
        visiting.add(module)
        for imported in records[module]["imports"]:
            walk(imported)
        visiting.remove(module)
        visited.add(module)

    for module in records:
        walk(module)
    return records, sorted(set(errors))


def file_map(root=ROOT):
    """Include every maintained file, with mechanically resolved code and schema links."""
    from build_skill_package import package_files

    records, errors = inspect_architecture(root)
    packaged = {p.relative_to(root).as_posix() for p in package_files()}
    files = []
    inventory = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for relative in sorted(set(inventory) - {""}):
        path = root / relative
        if not path.is_file():
            continue
        record = {"path": relative, "packaged": relative in packaged}
        if path.suffix == ".py":
            tree = ast.parse(path.read_text(encoding="utf-8"))
            record["imports"] = sorted(
                {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            )
        elif path.name.endswith("schema.json"):
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            record["schema_id"] = document.get("$id")
            record["definitions"] = sorted(document.get("$defs", {}))
        files.append(record)
    return {"files": files, "modules": records, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = file_map() if args.output else {"errors": inspect_architecture()[1]}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for error in result["errors"]:
        print(error)
    print(f"Architecture: {'FAIL' if result['errors'] else 'PASS'}")
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
