# ruff: noqa: E402
"""Final native identity proof through the generic adapter protocol, without GTM calls."""

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (
    AdapterExecutionError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from configuration_run import atomic_write, create_from_contract, load_document
from current_support import approve_mutations
from resource_registry import ResourceRegistryError, native_inventory_identity, normalized_family
from test_current_adapter_runtime import FakeAdapter, capabilities
from test_effective_configuration_guardrails import settings_contract

CASES = {
    "built-in variable": ("Click ID", "type", "clickId", {"type": "clickId"}),
    "container setting": ("Container", "containerId", None, {"notes": "Approved note"}),
    "destination": ("Destination", "destinationLinkId", "42", {"destinationId": "G-TEST123"}),
    "google tag configuration": (
        "Approved configuration",
        "gtagConfigId",
        "51",
        {"type": "test", "parameter": [{"type": "template", "key": "value", "value": "approved"}]},
    ),
    "workspace": ("Workspace", "workspaceId", None, {"description": "Approved description"}),
}


class NativeAdapter(FakeAdapter):
    def __init__(self, family, target, operation):
        super().__init__()
        self.bind_target(target)
        self.family = family
        self.reads = 0
        name, field, identity, fields = CASES[family]
        self.native = {
            "accountId": target["account_id"],
            "containerId": target["container_id"],
            **deepcopy(fields),
        }
        if family not in {"destination", "container setting"}:
            self.native["workspaceId"] = target["workspace_id"]
        self.native[field] = (
            identity or target["container_id" if family == "container setting" else "workspace_id"]
        )
        if family != "google tag configuration":
            self.native["name"] = name
        self.operation = operation
        self.listing = []
        self.written = False
        self.omit_saved_id = False

    def graph(self):
        # Existing protocol graph labels identify operations; gtag_config itself has no name.
        native = deepcopy(self.native)
        if self.omit_saved_id:
            native.pop("gtagConfigId", None)
        return {
            "objects": [
                {
                    **native,
                    "name": self.operation["name"],
                    "target_id": self.operation["target_id"],
                    "object_type": self.family,
                }
            ]
        }

    def read(self, operation):
        self.reads += 1
        return self.graph() if self.written else None

    def mutate(self, operation):
        self.written = True
        self.listing = [deepcopy(self.native)]
        return self.graph()

    def list_resource_page(self, family, cursor):
        return {"items": deepcopy(self.listing), "next_cursor": None}


class NativeInventoryFamilies(unittest.TestCase):
    def prepared(self, family, *, omit_saved_id=False):
        contract = settings_contract()
        name, _, _, fields = CASES[family]
        obj = contract["implementation"]["objects"][0]
        obj.update(
            resource_family=family,
            name=name,
            object_key=f"web-main::{family}::{name}",
            action="create",
            risk="high-impact",
            intended=deepcopy(fields),
        )
        obj.pop("pre_change", None)
        obj.pop("object_id", None)
        run = create_from_contract(
            approve_mutations(contract),
            run_id="native-families",
            source_locator="Synthetic approved native configuration",
        )
        target = run["run"]["targets"][0]
        adapter = NativeAdapter(family, target, run["object_changes"][0])
        adapter.omit_saved_id = omit_saved_id
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities(family))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "run.json"
        atomic_write(path, run)
        execute_ready_operations(path, registry)
        self.assertEqual(load_document(path)["object_changes"][0]["state"], "verified")
        return adapter, registry, path

    def test_complete_native_family_bodies_finish_without_extra_get(self):
        for family in CASES:
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                before = adapter.reads
                verify_idempotent_rerun(path, registry)
                self.assertEqual(load_document(path)["run"]["status"], "Configured")
                self.assertEqual(adapter.reads, before)

    def test_missing_native_identity_cannot_fall_back_to_get(self):
        for family, (_, field, _, _) in CASES.items():
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                adapter.listing[0].pop(field)
                before = adapter.reads
                with self.assertRaisesRegex(AdapterExecutionError, "native.*evidence|native scope"):
                    verify_idempotent_rerun(path, registry)
                self.assertEqual(adapter.reads, before)
                self.assertFalse(load_document(path)["idempotency"]["checked"])

    def test_partial_native_bodies_use_targeted_get(self):
        for family in ("destination", "google tag configuration", "workspace", "container setting"):
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                adapter.listing[0].pop(next(iter(CASES[family][3])))
                before = adapter.reads
                verify_idempotent_rerun(path, registry)
                self.assertEqual(adapter.reads, before + 1)
                self.assertEqual(load_document(path)["run"]["status"], "Configured")

    def test_native_name_to_distinct_id_conflicts_fail(self):
        for family in ("destination", "workspace", "built-in variable"):
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                duplicate = deepcopy(adapter.native)
                duplicate[CASES[family][1]] = (
                    "clickText" if family == "built-in variable" else "999"
                )
                adapter.listing.append(duplicate)
                with self.assertRaisesRegex(AdapterExecutionError, "Ambiguous"):
                    verify_idempotent_rerun(path, registry)
                self.assertFalse(load_document(path)["idempotency"]["checked"])

    def test_wrong_native_scope_fails_all_special_families(self):
        for family in CASES:
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                adapter.listing[0]["containerId"] = "different"
                with self.assertRaisesRegex(AdapterExecutionError, "native scope"):
                    verify_idempotent_rerun(path, registry)

    def test_workspace_scoped_selection_and_workspace_children_reject_wrong_workspace(self):
        for family in ("workspace", "built-in variable", "google tag configuration"):
            with self.subTest(family=family):
                adapter, registry, path = self.prepared(family)
                adapter.listing[0]["workspaceId"] = "another-workspace"
                with self.assertRaises(AdapterExecutionError):
                    verify_idempotent_rerun(path, registry)
                self.assertFalse(load_document(path)["idempotency"]["checked"])

    def test_nameless_configuration_rejects_changed_body(self):
        adapter, registry, path = self.prepared("google tag configuration")
        adapter.listing[0]["parameter"][0]["value"] = "unexpected"
        before = adapter.reads
        verify_idempotent_rerun(path, registry)
        self.assertFalse(load_document(path)["idempotency"]["checked"])
        self.assertEqual(adapter.reads, before)

    def test_nameless_configuration_requires_saved_native_id(self):
        adapter, registry, path = self.prepared("google tag configuration", omit_saved_id=True)
        before = adapter.reads
        with self.assertRaises(AdapterExecutionError):
            verify_idempotent_rerun(path, registry)
        self.assertEqual(adapter.reads, before)
        self.assertFalse(load_document(path)["idempotency"]["checked"])

    def test_canonical_spelling_and_native_identity_are_separate_from_reference_fields(self):
        from diff_object_graph import ID_FIELDS

        self.assertEqual(normalized_family("built-in variable"), "built-in variable")
        with self.assertRaises(ResourceRegistryError):
            normalized_family("built in variable")
        self.assertNotIn("containerId", ID_FIELDS)
        self.assertNotIn("workspaceId", ID_FIELDS)
        self.assertNotIn("gtagConfigId", ID_FIELDS)
        target = {"account_id": "1", "container_id": "2", "workspace_id": "3"}
        raw = {
            "accountId": "1",
            "containerId": "2",
            "destinationLinkId": "4",
            "destinationId": "G-123",
            "name": "Destination",
        }
        self.assertEqual(
            native_inventory_identity("destination", raw, target), ("Destination", "4")
        )


if __name__ == "__main__":
    unittest.main()
