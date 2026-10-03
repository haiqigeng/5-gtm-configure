"""Observed native representation regressions, with integrity and clearing guards."""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (  # noqa: E402
    RateLimitError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from adapter_support import AdapterExecutionError, AuthenticationError  # noqa: E402
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from current_support import approve_mutations, valid_web_contract  # noqa: E402
from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, bind, request  # noqa: E402
from mcp_adapter import McpTargetAdapter  # noqa: E402
from public_identifiers import canonical_template_source, public_identifier_paths  # noqa: E402
from redaction import contains_redacted, redact_for_persistence, sensitive_findings  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from test_google_ads_enhanced_conversions import event_override_contract  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402
from verification import (  # noqa: E402
    build_pre_write_comparison,
    build_verification_comparison,
    expected_graph,
)

SOURCE = '\ufeff\ufeff___INFO___\n{"id":"original", "name":"Fixture"}\n\n___WEB_PERMISSIONS___\n[{"key":"read", "value":true}]\n\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nconst x = 1;\n\n___TESTS___\nassertThat("test@example.org");\n'
NATIVE = '___INFO___\n{\n "name": "Fixture", "id": "original"\n}\n___WEB_PERMISSIONS___\n[ { "value": true, "key": "read" } ]\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nconst x = 1;\n___TESTS___\nassertThat("test@example.org");\n'


def operation(family="template"):
    op = {
        "operation_id": "op",
        "target_id": "web-main",
        "resource_family": family,
        "action": "create",
        "name": "Fixture",
        "object_key": f"web-main::{family}::Fixture",
        "container_type": "web",
        "intended": {},
    }
    if family == "template":
        op["intended"] = {"templateData": SOURCE}
        op["public_identifiers"] = [
            {
                "classification": "inspected-template-source",
                "path": ["templateData"],
                "value_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
            }
        ]
    return op


class NativeCorrectionsTests(unittest.TestCase):
    def test_template_native_representation_preserves_provenance_and_comparison(self):
        op = operation()
        saved = expected_graph(op)
        saved["objects"][0]["templateData"] = NATIVE.replace("\n", "\r\n")
        paths = public_identifier_paths(saved, records=[op])
        self.assertIn("$.objects[0].templateData", paths)
        comparison, retained = build_verification_comparison(op, saved)
        self.assertTrue(comparison["pass"], comparison)
        self.assertEqual(retained, saved)

    def test_code_permissions_info_arrays_and_bad_digest_never_gain_exemption(self):
        for changed in (
            NATIVE.replace("x = 1", "x = 2"),
            NATIVE.replace('"read"', '"write"'),
            NATIVE.replace('"original"', '"different"'),
            NATIVE + "___INFO___\n{}",
            NATIVE.replace('"id": "original"', '"id": "original", "id": "other"'),
        ):
            with self.subTest(changed=changed):
                op = operation()
                saved = expected_graph(op)
                saved["objects"][0]["templateData"] = changed
                self.assertFalse(public_identifier_paths(saved, records=[op]))
                self.assertFalse(build_verification_comparison(op, saved)[0]["pass"])
        op = operation()
        op["public_identifiers"][0]["value_sha256"] = "0" * 64
        self.assertFalse(public_identifier_paths({"templateData": NATIVE}, records=[op]))
        self.assertNotEqual(
            canonical_template_source(
                NATIVE.replace('[ { "value": true, "key": "read" } ]', "[1,2]")
            ),
            canonical_template_source(
                NATIVE.replace('[ { "value": true, "key": "read" } ]', "[2,1]")
            ),
        )

    def test_reviewed_template_still_redacts_real_credential(self):
        op = operation()
        source = SOURCE.replace(
            "const x = 1;", "const headers = {Authorization: 'Bearer secret-token-value'};"
        )
        op["intended"]["templateData"] = source
        op["public_identifiers"][0]["value_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        doc = expected_graph(op)
        self.assertTrue(
            contains_redacted(
                redact_for_persistence(
                    doc, public_identifier_paths=public_identifier_paths(doc, records=[op])
                )
            )
        )

    def test_empty_optional_parameter_readback_and_prewrite_only(self):
        op = operation("tag")
        op["intended"] = {"type": "gclidw", "parameter": []}
        original = deepcopy(op)
        saved = expected_graph(op)
        del saved["objects"][0]["parameter"]
        self.assertTrue(build_verification_comparison(op, saved)[0]["pass"])
        self.assertEqual(op, original)
        op["action"] = "update"
        op["pre_change"] = {"type": "gclidw", "parameter": []}
        self.assertTrue(
            build_pre_write_comparison(op, {"name": "Fixture", "type": "gclidw"})[0]["pass"]
        )
        saved["objects"][0]["parameter"] = [{"type": "template", "key": "retained", "value": "yes"}]
        self.assertFalse(build_verification_comparison(op, saved)[0]["pass"])
        for field in ("firingTriggerId", "blockingTriggerId"):
            op["intended"][field] = []
            self.assertFalse(build_verification_comparison(op, expected_graph(original))[0]["pass"])
            del op["intended"][field]

    def test_omission_descriptor_prose_but_not_personal_or_unknown_values(self):
        descriptor = {
            "source": "user_data",
            "source_shape": "object:matching",
            "destination_shape": "object:matching",
            "provenance": {"grade": "approved-input", "locator": "inputs/TASK.md"},
            "missing_behavior": "Omit absent fields.",
        }
        self.assertFalse(sensitive_findings({"user_data": descriptor}))
        for key, value in (
            ("missing_behavior", "Send to person@example.org"),
            ("unrecognized", "some value"),
            ("email", "person@example.org"),
        ):
            altered = {**descriptor, key: value}
            self.assertTrue(sensitive_findings({"user_data": altered}))

    def test_update_payload_retains_explicit_empty_parameter(self):
        req = request()
        backend = FakeGtm(req)
        adapter = McpTargetAdapter(req["targets"][0], PROFILE, backend.call)
        op = operation("tag")
        op["intended"] = {"type": "gclidw", "parameter": []}
        adapter.mutate(op)
        op["object_id"] = adapter.known_ids[op["object_key"]]
        op["action"] = "update"
        adapter.read(op)
        adapter.mutate(op)
        self.assertEqual(backend.calls[-1][1]["createOrUpdateConfig"]["parameter"], [])


if __name__ == "__main__":
    unittest.main()


class RecoveryCorrectionsTests(unittest.TestCase):
    def test_quota_retry_rechecks_native_delta_with_and_without_fingerprint(self):
        for fingerprint in (True, False):
            for drift in (True, False):
                with (
                    self.subTest(fingerprint=fingerprint, drift=drift),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    req = request()
                    backend = FakeGtm(req)
                    contract = compile_request(req)
                    path = Path(directory) / "create.json"
                    atomic_write(
                        path,
                        create_from_contract(contract, run_id="create", source_locator="synthetic"),
                    )
                    registry, _ = bind(contract, backend)
                    execute_ready_operations(path, registry)
                    saved = deepcopy(
                        next(
                            v
                            for v in backend.data["tag"].values()
                            if v["name"] == req["objects"][0]["name"]
                        )
                    )
                    if not fingerprint:
                        saved.pop("fingerprint")
                        backend.data["tag"][saved["tagId"]].pop("fingerprint")
                    update = request()
                    row = update["objects"][0]
                    row.update(
                        action="update", object_id=saved["tagId"], pre_change=deepcopy(saved)
                    )
                    row["intended"]["notes"] = "approved new note"
                    contract = compile_request(update)
                    path = Path(directory) / "update.json"
                    atomic_write(
                        path,
                        create_from_contract(contract, run_id="update", source_locator="synthetic"),
                    )
                    original_call = backend.call
                    attempts = []

                    def limited(tool, args):
                        if args["action"] == "update":
                            attempts.append(deepcopy(args))
                            if len(attempts) == 1:
                                raise RateLimitError("rejected quota", retry_after_seconds=0)
                        return original_call(tool, args)

                    backend.call = limited
                    registry, _ = bind(contract, backend)

                    def backoff(_):
                        if drift:
                            backend.data["tag"][saved["tagId"]]["notes"] = "concurrent edit"

                    execute_ready_operations(path, registry, sleep=backoff)
                    operation = next(
                        o
                        for o in load_document(path)["object_changes"]
                        if o["resource_family"] == "tag"
                    )
                    self.assertEqual(len(attempts), 1 if drift else 2)
                    self.assertEqual(operation["state"] == "verified", not drift)
                    if fingerprint and not drift:
                        self.assertEqual(attempts[1]["fingerprint"], saved["fingerprint"])

    def test_render_refuses_same_path_and_hardlink_without_touching_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(
                path,
                create_from_contract(
                    valid_web_contract(), run_id="render", source_locator="synthetic"
                ),
            )
            before = path.read_bytes()
            alias = Path(directory) / "alias.json"
            os.link(path, alias)
            for output in (path, alias):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/configuration_run.py"),
                        "render",
                        "--run",
                        str(path),
                        "--output",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(alias.read_bytes(), before)

    def test_recovered_drift_requires_fresh_convergence_without_losing_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            run = create_from_contract(
                valid_web_contract(), run_id="recovery", source_locator="synthetic"
            )
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            adapter = FakeAdapter()
            adapter.bind_target(run["run"]["targets"][0])
            registry = TargetAdapterRegistry()
            registry.register(run["run"]["targets"][0], adapter, capabilities("tag", "trigger"))
            execute_ready_operations(path, registry)
            before = deepcopy(adapter.saved)
            name = next(iter(adapter.saved))
            adapter.saved[name]["objects"][0]["notes"] = "drift"
            verify_idempotent_rerun(path, registry)
            failed_convergence = load_document(path)
            self.assertFalse(failed_convergence["idempotency"]["checked"])
            adapter.saved = before
            execute_ready_operations(path, registry)
            recovered = load_document(path)
            self.assertTrue(all(o["state"] == "verified" for o in recovered["object_changes"]))
            self.assertEqual(
                recovered["idempotency"],
                {"checked": False, "remaining_actions": [], "observations": []},
            )
            self.assertTrue(
                any(
                    j.get("convergence_repair")
                    for o in recovered["object_changes"]
                    for j in o["journal"]
                )
            )
            verify_idempotent_rerun(path, registry)
            self.assertTrue(load_document(path)["idempotency"]["checked"])


class NativeBindingTests(unittest.TestCase):
    def test_native_identity_is_verified_once_and_public_binding_is_immutable(self):
        req = request()
        backend = FakeGtm(req)
        target, profile = deepcopy(req["targets"][0]), deepcopy(PROFILE)
        adapter = McpTargetAdapter(target, profile, backend.call)
        expected = adapter.identity()
        target["workspace_id"] = "wrong"
        profile["tool_prefix"] = "wrong__"
        adapter.target["workspace_id"] = "wrong"
        adapter.profile["families"].clear()
        for name, replacement in (
            ("target", target),
            ("profile", profile),
            ("call", lambda *a: None),
        ):
            with self.assertRaises(AttributeError):
                setattr(adapter, name, replacement)
        for _ in range(124):
            self.assertEqual(adapter.identity(), expected)
        self.assertEqual(len(backend.calls), 2)
        adapter.list_resource_page("tag", None)
        self.assertEqual(backend.calls[-1][1]["workspaceId"], expected["workspace_id"])
        self.assertEqual(backend.calls[-1][0], "synthetic__gtm_tag")
        new_adapter = McpTargetAdapter(req["targets"][0], PROFILE, backend.call)
        new_adapter.identity()
        self.assertEqual(sum(a["action"] == "get" for _, a in backend.calls), 4)
        with self.assertRaises(AdapterExecutionError):
            adapter._call("gtm_tag", "get", workspaceId="wrong")

    def test_scope_requires_complete_metadata_or_exact_path_and_rejects_conflicts(self):
        req = request()
        adapter = McpTargetAdapter(req["targets"][0], PROFILE, lambda *a: {})
        scope = {
            "accountId": "account-1",
            "containerId": "GTM-WEBTEST",
            "workspaceId": "workspace-web",
        }
        path = "accounts/account-1/containers/GTM-WEBTEST/workspaces/workspace-web/tags/42"
        for raw in (scope, {"path": path}, {**scope, "path": path}):
            adapter._check_scope(raw)
        for raw in (
            {},
            {"accountId": "account-1"},
            {**scope, "workspaceId": "wrong"},
            {**scope, "path": path.replace("/42", "/42/extra")},
            {**scope, "path": path.replace("workspace-web", "wrong")},
            {"path": path, "accountId": "wrong"},
        ):
            with self.assertRaises(AdapterExecutionError):
                adapter._check_scope(raw)

    def test_identity_mismatch_is_not_cached_and_reconnect_auth_still_fails(self):
        req = request()
        backend = FakeGtm(req)
        changed = {"bad": True, "denied": False}

        def call(tool, args):
            if changed["denied"]:
                return {"isError": True, "structuredContent": {"error": {"code": 401}}}
            result = backend.call(tool, args)
            if changed["bad"] and tool.endswith("gtm_workspace"):
                result["workspaceId"] = "wrong"
            return result

        adapter = McpTargetAdapter(req["targets"][0], PROFILE, call)
        with self.assertRaises(AdapterExecutionError):
            adapter.identity()
        changed["bad"] = False
        adapter.identity()
        changed["denied"] = True
        with self.assertRaises(AuthenticationError):
            adapter.list_resource_page("tag", None)
        with self.assertRaises(AuthenticationError):
            adapter.mutate(operation("tag"))


def meta_matching_contract(fields=("em", "ph")):
    contract = event_override_contract()
    req = contract["requirements"][0]
    req["destination"] = "Meta"
    original = deepcopy(req["parameters"]["user_data"])
    req["parameters"] = {}
    tag = contract["implementation"]["objects"][0]
    tag["intended"]["type"] = "cvt_meta"
    rows = []
    bindings = []
    routes = []
    original_route = deepcopy(contract["first_party_data_routes"][0])
    objects = contract["implementation"]["objects"]
    removed = {o["object_key"] for o in objects if o["intended"].get("type") == "awec"}
    objects[:] = [o for o in objects if o["object_key"] not in removed]
    tag["depends_on"] = [k for k in tag["depends_on"] if k not in removed]
    email = next(o for o in objects if o["name"] == "DLV - Approved email")
    tag["depends_on"].append(email["object_key"])
    if "ph" in fields:
        phone = deepcopy(email)
        phone.update(
            name="DLV - Approved phone", object_key="web-main::variable::DLV - Approved phone"
        )
        phone["intended"]["parameter"][0]["value"] = "customer.phone"
        objects.append(phone)
        tag["depends_on"].append(phone["object_key"])
    for index, name in enumerate(fields):
        source = "customer.email" if name == "em" else "customer.phone"
        reference = "{{DLV - Approved email}}" if name == "em" else "{{DLV - Approved phone}}"
        req["parameters"][name] = {
            **original,
            "source": source,
            "source_shape": "scalar",
            "destination_shape": "scalar",
        }
        rows.append(
            {
                "type": "map",
                "map": [
                    {"type": "template", "key": "name", "value": name},
                    {"type": "template", "key": "value", "value": reference},
                ],
            }
        )
        binding = deepcopy(contract["implementation"]["field_bindings"][0])
        binding.update(
            destination_field=name,
            gtm_resolution=reference,
            template_field="advancedMatchingList:" + name,
        )
        bindings.append(binding)
        route = deepcopy(original_route)
        route.update(
            feature="vendor-advanced-matching",
            destination_field=name,
            fields=[
                {
                    "name": name,
                    "source": source,
                    "normalization": ["native"],
                    "empty_behavior": "omit",
                }
            ],
        )
        route["consumer_bindings"][0].update(
            product="meta",
            implementation="installed-template",
            tag_type="cvt_meta",
            template_identity="cvt_meta",
            user_data_path=[
                "parameter",
                "advancedMatchingList",
                "list",
                index,
                "map",
                "value",
                "value",
            ],
            activation_paths=[["parameter", "advancedMatching", "value"]],
        )
        routes.append(route)
    tag["intended"]["parameter"] = [
        {"type": "boolean", "key": "advancedMatching", "value": "true"},
        {"type": "list", "key": "advancedMatchingList", "list": rows},
    ]
    contract["implementation"]["field_bindings"] = bindings
    contract["first_party_data_routes"] = routes
    contract["consent_topologies"][0]["destination"] = "Meta"
    contract["execution_topologies"][0]["built_in_consent_checks"] = []
    return approve_mutations(contract)


class MatchingCorrectionsTests(unittest.TestCase):
    def test_complete_contract_single_and_two_matching_fields(self):
        for fields in (("em",), ("em", "ph")):
            contract = meta_matching_contract(fields)
            validate_document(contract)
            run = create_from_contract(contract, run_id="matching", source_locator="synthetic")
            self.assertEqual(len(run["first_party_data_routes"]), len(fields))

    def test_matching_duplicates_wrong_row_source_timing_and_disabled_control_rejected(self):
        for flaw in ("duplicate", "row", "source", "timing", "disabled", "table-alias", "value"):
            contract = meta_matching_contract()
            route = contract["first_party_data_routes"][0]
            if flaw == "duplicate":
                contract["first_party_data_routes"].append(deepcopy(route))
            elif flaw == "row":
                route["consumer_bindings"][0]["user_data_path"][3] = 1
            elif flaw == "source":
                route["fields"][0]["source"] = "wrong.source"
            elif flaw == "timing":
                route["timing"] = "prior-page"
            elif flaw == "disabled":
                contract["implementation"]["objects"][0]["intended"]["parameter"][0]["value"] = (
                    "false"
                )
            elif flaw == "table-alias":
                route["destination_field"] = "advancedMatchingList"
            else:
                contract["implementation"]["field_bindings"][0]["gtm_resolution"] = (
                    "{{Wrong variable}}"
                )
            with self.subTest(flaw=flaw), self.assertRaises(ContractValidationError):
                validate_document(approve_mutations(contract))
