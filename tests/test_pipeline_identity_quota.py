"""Focused offline regressions for native pipeline identity and typed GTM quota refusal."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import test_current_adapter_runtime as runtime_tests  # noqa: E402
from adapter_support import (  # noqa: E402
    AdapterExecutionError,
    AmbiguousWriteError,
    RateLimitError,
    collect_paginated,
)
from configuration_run import create_from_contract  # noqa: E402
from current_support import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    approve_mutations,
    valid_pipeline_contract,
    valid_web_contract,
)
from mcp_adapter import unwrap  # noqa: E402
from shared_event_id import validate_pipeline_dedup  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from test_shared_event_id import generated_contract  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402


def quota():
    return {
        "isError": True,
        "structuredContent": {"error": {"code": 403, "errors": [{"reason": "rateLimitExceeded"}]}},
    }


class PipelineIdentityTest(unittest.TestCase):
    def test_supplied_and_generated_positive_baselines(self):
        for contract in (
            add_nonpurchase_dual_dedup(valid_pipeline_contract()),
            generated_contract(),
        ):
            validate_document(approve_mutations(contract))
            create_from_contract(
                contract, run_id="positive-identity", source_locator="offline fixture"
            )

    def assert_rejected(self, contract):
        with self.assertRaises(ContractValidationError):
            validate_document(approve_mutations(contract))
        errors = []
        validate_pipeline_dedup(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["pipelines"],
            errors.append,
        )
        self.assertTrue(errors)

    def test_supplied_and_generated_bindings_reject_metadata_and_unrelated_fields(self):
        for factory in (
            lambda: add_nonpurchase_dual_dedup(valid_pipeline_contract()),
            generated_contract,
        ):
            for role in ("browser_consumer_keys", "transporter_consumer_keys"):
                for field in ("notes", "unrelated", "event_id"):
                    with self.subTest(factory=factory, role=role, field=field):
                        contract = factory()
                        dedup = contract["dedup_contracts"][0]
                        key = dedup[role][0]
                        tag = next(
                            o
                            for o in contract["implementation"]["objects"]
                            if o["object_key"] == key
                        )
                        tag["intended"]["event_id"] = "wrong-id"
                        if field == "notes":
                            tag["intended"][field] = dedup["source_reference"]
                        if field == "unrelated":
                            tag["intended"]["parameter"] = [
                                {
                                    "type": "template",
                                    "key": "unrelated",
                                    "value": dedup["source_reference"],
                                }
                            ]
                        bindings = dedup.get("generation", dedup)["consumer_bindings"]
                        next(b for b in bindings if b["object_key"] == key)["field_path"] = (
                            ["parameter", "unrelated", "value"] if field == "unrelated" else [field]
                        )
                        self.assert_rejected(contract)

    def test_receiver_ownership_does_not_include_unrelated_destinations(self):
        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        pipeline = contract["pipelines"][0]
        flow = next(f for f in pipeline["event_flows"] if f["requirement_id"] == "REQ-ATC")
        unrelated = {
            "object_key": "server-main::tag::Unrelated",
            "resource_family": "tag",
            "target_id": "server-main",
            "intended": {"type": "ga4"},
        }
        contract["implementation"]["objects"].append(unrelated)
        flow["server_consumer_keys"].append(unrelated["object_key"])
        errors = []
        validate_pipeline_dedup(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["pipelines"],
            errors.append,
        )
        self.assertEqual(errors, [])
        pipeline["field_flows"] = [
            f for f in pipeline["field_flows"] if f["destination_field"] != "event_id"
        ]
        validate_pipeline_dedup(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["pipelines"],
            errors.append,
        )
        self.assertTrue(errors)

    def test_receiver_requires_exact_event_data_variable_without_regeneration(self):
        for factory in (
            lambda: add_nonpurchase_dual_dedup(valid_pipeline_contract()),
            generated_contract,
        ):
            for defect in ("wrong-path", "generator", "literal", "notes"):
                contract = factory()
                objects = contract["implementation"]["objects"]
                variable = next(o for o in objects if o["name"] == "Event Data - event_id")
                tag = next(o for o in objects if o["name"] == "Meta CAPI - add_to_cart")
                if defect == "wrong-path":
                    variable["intended"]["parameter"][0]["value"] = "another_id"
                elif defect == "generator":
                    variable["intended"]["type"] = "cvt_generator"
                elif defect == "literal":
                    tag["intended"]["event_id"] = "independent-id"
                else:
                    tag["intended"]["notes"] = tag["intended"].pop("event_id")
                self.assert_rejected(contract)

    def test_inherited_native_event_table_identity_and_override(self):
        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        dedup = contract["dedup_contracts"][0]
        objects = contract["implementation"]["objects"]
        tag = next(o for o in objects if o["object_key"] == dedup["transporter_consumer_keys"][0])
        settings = deepcopy(
            next(o for o in objects if o["object_key"] == dedup["source_variable_key"])
        )
        settings.update(
            name="Shared event settings", object_key="web-main::variable::Shared event settings"
        )
        settings["intended"] = {
            "type": "gtes",
            "parameter": [
                {
                    "type": "list",
                    "key": "eventSettingsTable",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                {"type": "template", "key": "parameter", "value": "event_id"},
                                {
                                    "type": "template",
                                    "key": "parameterValue",
                                    "value": dedup["source_reference"],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        settings["depends_on"] = [dedup["source_variable_key"]]
        settings["risk"] = "high-impact"
        objects.append(settings)
        tag["depends_on"].append(settings["object_key"])
        tag["intended"].pop("event_id")
        tag["intended"]["parameter"] = [
            {
                "type": "template",
                "key": "eventSettingsVariable",
                "value": "{{Shared event settings}}",
            }
        ]
        validate_document(approve_mutations(contract))
        create_from_contract(
            contract, run_id="native-inherited-id", source_locator="offline fixture"
        )
        tag["intended"]["event_id"] = "overridden-id"
        self.assert_rejected(contract)


class QuotaTest(unittest.TestCase):
    def test_only_typed_rate_reasons_are_retryable(self):
        for reason in ("rateLimitExceeded", "userRateLimitExceeded"):
            response = quota()
            response["structuredContent"]["error"]["errors"][0]["reason"] = reason
            for mutation in (False, True):
                with self.assertRaises(RateLimitError) as caught:
                    unwrap(response, mutation=mutation)
                self.assertEqual(caught.exception.retry_after_seconds, 100)
        for reasons in (
            [],
            [{"reason": "forbidden"}],
            [{"reason": "dailyLimitExceeded"}],
            [{"reason": "rateLimitExceeded"}, {"reason": "forbidden"}],
        ):
            response = quota()
            response["structuredContent"]["error"].update(
                errors=reasons, message="rateLimitExceeded"
            )
            with self.assertRaises(AdapterExecutionError) as caught:
                unwrap(response, mutation=True)
            self.assertNotIsInstance(caught.exception, RateLimitError)
        with self.assertRaises(AmbiguousWriteError):
            unwrap(
                {"isError": True, "content": [{"type": "text", "text": "403 rateLimitExceeded"}]},
                mutation=True,
            )

    def test_discovery_page_quota_wait_and_bound(self):
        calls, delays = [], []

        def page(cursor):
            calls.append(cursor)
            if len(calls) == 1:
                unwrap(quota())
            return {"items": [{"name": "one"}], "next_cursor": None}

        self.assertEqual(collect_paginated(page, sleep=delays.append), [{"name": "one"}])
        self.assertEqual(delays, [100])
        delays.clear()
        with self.assertRaises(RateLimitError):
            collect_paginated(lambda _: unwrap(quota()), sleep=delays.append)
        self.assertEqual(delays, [100, 100])
        delays.clear()
        with self.assertRaises(RateLimitError):
            collect_paginated(
                lambda _: unwrap(quota()), sleep=delays.append, max_retry_delay_seconds=2
            )
        self.assertEqual(delays, [])

    def test_mutation_refusal_retries_but_readback_never_replays_write(self):
        for phase in ("mutation", "readback", "exhausted-readback"):

            class Adapter(FakeAdapter):
                refused = False

                def mutate(self, operation):
                    if (
                        operation["resource_family"] == "tag"
                        and phase == "mutation"
                        and not self.refused
                    ):
                        self.refused = True
                        unwrap(quota(), mutation=True)
                    return super().mutate(operation)

                def read(self, operation):
                    if (
                        operation["resource_family"] == "tag"
                        and operation["name"] in self.saved
                        and phase != "mutation"
                    ):
                        if phase == "exhausted-readback" or not self.refused:
                            self.refused = True
                            unwrap(quota())
                    return super().read(operation)

            adapter, delays = Adapter(), []
            run, _ = runtime_tests.CurrentAdapterRuntimeTest()._execute(
                valid_web_contract(),
                {"web-main": (adapter, capabilities("tag", "trigger"), None)},
                sleep=delays.append,
            )
            self.assertEqual(
                adapter.mutations.count("Google tag - Web transport"),
                1,
                (phase, run["object_changes"], delays),
            )
            self.assertEqual(
                run["object_changes"][0]["state"],
                "uncertain" if phase == "exhausted-readback" else "verified",
            )
            self.assertTrue(delays)
            self.assertTrue(all(delay == 100 for delay in delays))
