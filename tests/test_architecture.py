"""Release gates reject structural ownership regressions in synthetic modules."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from check_architecture import inspect_architecture
from check_release import check_files_and_routing


def write_module(root, name, source):
    path = root / "scripts" / Path(*name.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_duplicate_constant_owner_is_rejected(tmp_path):
    for name in ("core.model", "domain.model"):
        write_module(tmp_path, "gtm_configure." + name, "MODES = {'a', 'b'}\nprint(MODES)\n")
    assert any(
        "duplicate constant owner MODES" in error for error in inspect_architecture(tmp_path)[1]
    )


def test_dependency_cycle_and_layer_inversion_are_rejected(tmp_path):
    write_module(
        tmp_path, "gtm_configure.core.value", "import gtm_configure.domain.value as other\n"
    )
    write_module(
        tmp_path, "gtm_configure.domain.value", "import gtm_configure.core.value as other\n"
    )
    errors = inspect_architecture(tmp_path)[1]
    assert any("dependency cycle" in error for error in errors)
    assert any("inverted dependency" in error for error in errors)


def test_private_cross_module_access_is_rejected(tmp_path):
    write_module(tmp_path, "gtm_configure.domain.owner", "def _inspect():\n    return 1\n")
    write_module(
        tmp_path,
        "gtm_configure.domain.caller",
        "import gtm_configure.domain.owner as owner\nowner._inspect()\n",
    )
    assert any("private access" in error for error in inspect_architecture(tmp_path)[1])


def test_unreferenced_definition_is_rejected(tmp_path):
    write_module(
        tmp_path, "gtm_configure.domain.owner", "RETIRED = {'old'}\ndef retired():\n    return 1\n"
    )
    errors = inspect_architecture(tmp_path)[1]
    assert any("unreferenced constant" in error for error in errors)
    assert any("unreferenced definition" in error for error in errors)


def test_link_label_tracks_its_file_target(tmp_path):
    (tmp_path / "references").mkdir()
    (tmp_path / "references/current.md").write_text("# Current\n")
    (tmp_path / "SKILL.md").write_text("[retired.md](references/current.md)\n")
    with patch("check_release.ROOT", tmp_path):
        assert any("file label" in error for error in check_files_and_routing())


@pytest.mark.parametrize(
    "keys",
    [
        ["pages_read", "exhausted"],
        ["operation_id", "target_id", "state", "journal", "dependencies"],
    ],
)
def test_local_closed_record_copy_is_rejected(tmp_path, keys):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: {} for key in keys},
    }
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/run.schema.json").write_text(json.dumps(schema))
    write_module(
        tmp_path,
        "gtm_configure.runtime.reader",
        f"def read(row):\n    fields = {set(keys)!r}\n    return set(row) - fields\nread({{}})\n",
    )
    assert any(
        "duplicated schema record keys" in error for error in inspect_architecture(tmp_path)[1]
    )
