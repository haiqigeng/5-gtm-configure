"""Current instructions and schema titles stay bound to the executable schema version."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import check_release


def test_current_claims_checked_across_instruction_and_schema_boundaries(tmp_path, monkeypatch):
    versions = {
        "contract": check_release.CONTRACT_SCHEMA_VERSION,
        "run": check_release.SCHEMA_VERSION,
    }
    monkeypatch.setattr(check_release, "ROOT", tmp_path)
    (tmp_path / "references" / "core").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion="{check_release.CURRENT_RELEASE}"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(f"v{check_release.CURRENT_RELEASE}", encoding="utf-8")
    skill = tmp_path / "SKILL.md"
    reference = tmp_path / "references" / "core" / "execution.md"
    skill.write_text(f"Use configuration-contract@{versions['contract']}.", encoding="utf-8")
    reference.write_text(f"Use configuration-run@{versions['run']}.", encoding="utf-8")
    schemas = {
        kind: {
            "title": f"configure-gtm configuration-{kind}@{version}",
            "properties": {"schema_version": {"const": version}},
        }
        for kind, version in versions.items()
    }
    monkeypatch.setattr(
        check_release,
        "validator",
        lambda kind: SimpleNamespace(schema=schemas[kind], check_schema=lambda schema: None),
    )
    assert check_release.check_versions_and_schemas() == []
    skill.write_text("Use configuration-contract@0.0.", encoding="utf-8")
    reference.write_text("Use configuration-run@0.0.", encoding="utf-8")
    schemas["contract"]["title"] = "configure-gtm configuration-contract@0.0"
    errors = check_release.check_versions_and_schemas()
    assert len(errors) == 3
    assert any("SKILL.md" in error for error in errors)
    assert any("execution.md" in error for error in errors)
    assert any("contract schema title" in error for error in errors)
    (tmp_path / "release-notes").mkdir()
    (tmp_path / "release-notes" / "old.md").write_text(
        json.dumps({"title": "contract@0.0"}), encoding="utf-8"
    )
    assert check_release.check_versions_and_schemas() == errors
