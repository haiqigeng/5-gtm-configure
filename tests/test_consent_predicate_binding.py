from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from configuration_run import create_from_contract  # noqa: E402
from current_support import approve_mutations, valid_web_contract  # noqa: E402
from run_validation_web import (  # noqa: E402
    RunValidationError,
    _validate_execution_topologies,
)
from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
    validate_document,
)


def condition(operator: str, source: str, value: object, **flags: object) -> dict:
    """Actual GTM REST Condition rows, including string-encoded boolean flags."""
    return {
        "type": operator,
        "parameter": [
            {"type": "template", "key": "arg0", "value": source},
            {"type": "template", "key": "arg1", "value": value},
            *[{"type": "boolean", "key": key, "value": flag} for key, flag in flags.items()],
        ],
    }


def grant(**flags: object) -> dict:
    # An opaque source name ensures detection does not depend on consent/CMP keywords.
    return condition("contains", "{{DLV - State}}", ",vendor-42,", **flags)


class ConsentPredicateBindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.normal = {
            "type": "customEvent",
            "customEventFilter": [condition("equals", "{{_event}}", "purchase")],
            "filter": [],
        }
        self.block = {
            "type": "customEvent",
            "customEventFilter": [condition("matchRegex", "{{_event}}", ".*")],
            "filter": [grant(negate="true")],
        }
        self.tag = {
            "type": "gaawe",
            "eventName": "purchase",
            "firingTriggerId": ["trigger::Source"],
            "blockingTriggerId": ["trigger::Vendor block"],
        }
        self.operations = {
            key: {
                "operation_id": key,
                "object_key": key,
                "object_type": key.split("::")[0],
                "action": "create",
                "requirement_ids": ["REQ-1"],
                "intended": intended,
            }
            for key, intended in (
                ("tag::Measurement", self.tag),
                ("trigger::Source", self.normal),
                ("trigger::Vendor block", self.block),
            )
        }
        self.topology = {
            "tag_object_key": "tag::Measurement",
            "requirement_ids": ["REQ-1"],
            "lifecycle_role": "event-driven",
            "normal_triggers": [
                {
                    "trigger_object_key": "trigger::Source",
                    "role": "source-event",
                    "type": "custom-event",
                },
            ],
            "consent_mode": "strict-basic",
            "blocking_trigger_keys": ["trigger::Vendor block"],
            "blocking_event_scope": ".*",
            "built_in_consent_checks": ["analytics_storage"],
            "additional_consent_checks": [],
            "firing_option": "once-per-event",
            "may_precede_cmp": False,
            "pre_cmp_policy": "not-applicable",
            "page_view_capable": False,
            "page_view_destinations": [],
            "page_view_occurrences": [],
            "ecommerce_route": "not-applicable",
            "manual_ecommerce_fields": [],
            "evidence": ["Synthetic offline GTM Condition fixture"],
        }

    def validate(self) -> dict:
        return _validate_execution_topologies(
            [self.topology],
            requirement_ids={"REQ-1"},
            operations=self.operations,
            baseline_trigger_types={},
        )

    def test_valid_business_filters_and_native_plus_block_are_preserved(self) -> None:
        self.normal["filter"] = [
            condition("equals", "{{Page Hostname}}", "shop.example.test"),
            condition("equals", "{{DLV - Environment}}", "production"),
            condition("greater", "{{DLV - Order value}}", "0"),
        ]
        # Sharing the same positive host scope is not duplicate consent eligibility.
        self.block["filter"].append(deepcopy(self.normal["filter"][0]))
        before = deepcopy((self.operations, self.topology))
        self.assertEqual(self.validate()["tag::Measurement"], self.topology)
        self.assertEqual((self.operations, self.topology), before)

    def test_cmp_lifecycle_and_source_event_selectors_are_preserved(self) -> None:
        for selector in (
            "cmp_consent_granted",
            [condition("equals", "{{Event}}", "cmp_consent_granted")],
        ):
            with self.subTest(selector=selector):
                self.normal["customEventFilter"] = selector
                self.topology["lifecycle_role"] = "baseline-page-load"
                self.topology["normal_triggers"][0]["role"] = "cmp-readiness-grant"
                before = deepcopy((self.operations, self.topology))
                self.validate()
                self.assertEqual((self.operations, self.topology), before)

    def test_complementary_raw_predicates_are_rejected_for_both_lifecycles(self) -> None:
        for lifecycle, role in (
            ("event-driven", "source-event"),
            ("baseline-page-load", "cmp-readiness-grant"),
        ):
            with self.subTest(lifecycle=lifecycle):
                self.topology["lifecycle_role"] = lifecycle
                self.topology["normal_triggers"][0]["role"] = role
                self.normal["filter"] = [grant()]
                with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
                    self.validate()

    def test_native_condition_operators_and_negation_are_compared(self) -> None:
        for operator, operand in (
            ("equals", "granted"),
            ("contains", ",vendor-42,"),
            ("startsWith", "granted:"),
            ("endsWith", ":granted"),
            ("matchRegex", "(^|,)vendor-42(,|$)"),
            ("greater", "0"),
        ):
            with self.subTest(operator=operator):
                self.normal["filter"] = [condition(operator, "{{DLV - State}}", operand)]
                self.block["filter"] = [
                    condition(operator, "{{DLV - State}}", operand, negate="true")
                ]
                with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
                    self.validate()

    def test_parameter_order_and_boolean_encoding_do_not_hide_a_duplicate(self) -> None:
        for false, true in ((False, True), ("false", "true")):
            with self.subTest(false=false, true=true):
                self.normal["filter"] = [
                    condition("matchRegex", "{{DLV - State}}", "^granted$", ignore_case=true),
                ]
                self.block["filter"] = [
                    condition(
                        "matchRegex", "{{DLV - State}}", "^granted$", ignore_case=true, negate=true
                    ),
                ]
                self.normal["filter"][0]["parameter"].append(
                    {"type": "boolean", "key": "negate", "value": false}
                )
                self.block["filter"][0]["parameter"].reverse()
                with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
                    self.validate()

    def test_default_false_flags_and_reversed_polarity_are_recognized(self) -> None:
        self.normal["filter"] = [
            condition("matchRegex", "{{DLV - State}}", "denied", negate="true"),
        ]
        self.block["filter"] = [
            condition("matchRegex", "{{DLV - State}}", "denied", ignore_case="false"),
        ]
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
            self.validate()

    def test_distinct_business_or_consent_predicates_are_not_equated(self) -> None:
        for normal in (
            condition("contains", "{{DLV - Other state}}", ",vendor-42,"),
            condition("contains", "{{DLV - State}}", ",vendor-420,"),
            condition("equals", "{{DLV - State}}", ",vendor-42,"),
            condition("equals", "{{Page Hostname}}", "shop.example.test"),
        ):
            with self.subTest(normal=normal):
                self.normal["filter"] = [normal]
                self.validate()

    def test_regex_case_and_operand_types_are_not_silently_coerced(self) -> None:
        for normal, block in (
            (
                condition("matchRegex", "{{DLV - State}}", "GRANTED", ignore_case=True),
                condition("matchRegex", "{{DLV - State}}", "GRANTED", negate=True),
            ),
            (
                condition("equals", "{{DLV - State}}", True),
                condition("equals", "{{DLV - State}}", "true", negate=True),
            ),
        ):
            with self.subTest(normal=normal):
                self.normal["filter"], self.block["filter"] = [normal], [block]
                self.validate()

    def test_common_business_scope_does_not_hide_a_duplicate(self) -> None:
        host = condition("equals", "{{Page Hostname}}", "shop.example.test")
        self.normal["filter"] = [host, grant()]
        self.block["filter"].append(deepcopy(host))
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
            self.validate()

    def test_partial_overlap_with_an_and_block_is_not_equivalence(self) -> None:
        # The host filter is valid business scope. Removing it would broaden firing:
        # NOT(host-not-shop AND consent-denied) does not require host-is-shop.
        self.normal["filter"] = [condition("equals", "{{Page Hostname}}", "shop.example.test")]
        self.block["filter"].append(
            condition("equals", "{{Page Hostname}}", "shop.example.test", negate=True)
        )
        self.validate()

    def test_narrow_exception_scope_does_not_justify_removing_a_firing_condition(self) -> None:
        self.normal["filter"] = [grant()]
        self.block["customEventFilter"] = [condition("equals", "{{_event}}", "cmp_ready")]
        self.validate()
        self.block["customEventFilter"] = [condition("equals", "{{Event}}", "purchase")]
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
            self.validate()

    def test_event_constraints_in_all_filter_arrays_limit_exception_coverage(self) -> None:
        self.normal["filter"] = [grant()]
        self.block["filter"].append(condition("equals", "{{_event}}", "cmp_ready"))
        self.validate()
        self.block["filter"][-1] = condition("equals", "{{_event}}", "purchase")
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
            self.validate()

    def test_condition_arrays_are_inspected_without_treating_event_names_as_consent(self) -> None:
        for field in ("filter", "autoEventFilter", "customEventFilter"):
            with self.subTest(field=field):
                self.setUp()
                self.normal.setdefault(field, []).append(grant())
                with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
                    self.validate()
        self.setUp()
        self.normal["filter"] = [condition("equals", "{{_event}}", "consent_granted")]
        self.block["filter"] = [condition("equals", "{{_event}}", "consent_granted", negate=True)]
        self.validate()

    def test_every_attached_normal_and_block_is_inspected(self) -> None:
        extra = deepcopy(self.operations["trigger::Source"])
        extra.update(operation_id="extra", object_key="trigger::Second source")
        extra["intended"]["filter"] = [grant()]
        self.operations["extra"] = extra
        self.tag["firingTriggerId"].append(extra["object_key"])
        self.topology["normal_triggers"].append(
            {
                "trigger_object_key": extra["object_key"],
                "type": "custom-event",
                "role": "source-event",
            }
        )
        self.tag["blockingTriggerId"].insert(0, "trigger::Other block")
        self.topology["blocking_trigger_keys"].insert(0, "trigger::Other block")
        other = deepcopy(self.operations["trigger::Vendor block"])
        other.update(operation_id="other", object_key="trigger::Other block")
        other["intended"]["filter"] = [
            condition("equals", "{{DLV - Other state}}", "granted", negate=True)
        ]
        self.operations["other"] = other
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate") as caught:
            self.validate()
        self.assertIn("trigger::Second source", str(caught.exception))
        self.assertIn("trigger::Vendor block", str(caught.exception))
        self.assertIn("filter[0]", str(caught.exception))

    def test_unattached_trigger_and_pre_change_do_not_override_intended_filters(self) -> None:
        unused = deepcopy(self.operations["trigger::Source"])
        unused.update(operation_id="unused", object_key="trigger::Unrelated")
        unused["intended"]["filter"] = [grant()]
        self.operations["unused"] = unused
        self.operations["trigger::Source"]["pre_change"] = deepcopy(unused["intended"])
        self.operations["trigger::Source"]["action"] = "update"
        self.validate()

    def test_reused_and_untouched_trigger_snapshots_are_inspected(self) -> None:
        for action in ("reuse", "untouched"):
            with self.subTest(action=action):
                self.setUp()
                self.normal["filter"] = [grant()]
                for key in ("trigger::Source", "trigger::Vendor block"):
                    operation = self.operations[key]
                    operation["action"] = action
                    operation["pre_change"] = operation.pop("intended")
                with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
                    self.validate()

    def test_invented_google_native_checks_are_rejected_by_actual_tag_class(self) -> None:
        for tag_type in (
            "googtag",
            "Google tag",
            "gaawc",
            "gaawe",
            "GA4 Event",
            "awct",
            "sp",
            "flc",
            "fls",
            "gclidw",
        ):
            with self.subTest(tag_type=tag_type):
                self.tag["type"] = tag_type
                self.topology["built_in_consent_checks"] = ["invented_vendor_consent"]
                with self.assertRaisesRegex(RunValidationError, "built_in_consent_checks.*Google"):
                    self.validate()

    def test_google_native_checks_can_coexist_with_strict_basic_vendor_block(self) -> None:
        for tag_type, checks in (
            ("googtag", ["analytics_storage", "ad_storage", "ad_user_data", "ad_personalization"]),
            ("gaawe", ["analytics_storage"]),
            ("awct", ["ad_storage", "ad_user_data"]),
            ("sp", ["ad_storage", "ad_personalization"]),
            ("flc", ["ad_storage"]),
            ("fls", ["ad_storage"]),
            ("gclidw", ["ad_storage"]),
        ):
            with self.subTest(tag_type=tag_type):
                self.tag["type"] = tag_type
                self.topology["built_in_consent_checks"] = checks
                self.validate()

    def test_custom_template_consent_types_are_not_restricted_to_google_names(self) -> None:
        for tag_type in ("cvt_123_456", "Google partner custom template", "baut"):
            with self.subTest(tag_type=tag_type):
                self.tag["type"] = tag_type
                self.topology["built_in_consent_checks"] = [
                    "vendor_measurement",
                    "functionality_storage",
                ]
                self.validate()

    def test_additional_consent_checks_remain_distinct_from_native_behavior(self) -> None:
        self.tag["consentSettings"] = {
            "consentStatus": "needed",
            "consentType": {
                "type": "list",
                "list": [
                    {"type": "template", "value": "analytics_storage"},
                ],
            },
        }
        self.topology["additional_consent_checks"] = ["analytics_storage"]
        with self.assertRaisesRegex(RunValidationError, "must be empty under strict-basic"):
            self.validate()

    def test_advanced_native_behavior_still_requires_no_defeating_block(self) -> None:
        self.topology["consent_mode"] = "advanced-native"
        with self.assertRaisesRegex(RunValidationError, "must not carry a defeating block"):
            self.validate()
        self.topology["blocking_trigger_keys"] = []
        self.topology["blocking_event_scope"] = None
        self.tag["blockingTriggerId"] = []
        self.validate()

    def test_public_contract_and_materialization_use_the_predicate_gate(self) -> None:
        contract = valid_web_contract()
        topology = contract["execution_topologies"][0]
        objects = {item["object_key"]: item for item in contract["implementation"]["objects"]}
        normal = objects[topology["normal_triggers"][0]["trigger_object_key"]]["intended"]
        block = objects[topology["blocking_trigger_keys"][0]]["intended"]
        normal["customEventFilter"] = [condition("equals", "{{_event}}", "cmp_analytics_granted")]
        block["customEventFilter"] = [condition("matchRegex", "{{_event}}", ".*")]
        block["filter"] = [grant(negate="true")]
        normal["filter"] = [condition("equals", "{{Page Hostname}}", "shop.example.test")]
        approve_mutations(contract)
        validate_document(contract)
        run = create_from_contract(contract, run_id="CONSENT-BINDING", source_locator="synthetic")
        self.assertEqual(run["schema_version"], "4.0")
        normal["filter"].append(grant())
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "duplicated consent predicate"):
            validate_document(contract)
        with self.assertRaisesRegex(RunValidationError, "duplicated consent predicate"):
            create_from_contract(contract, run_id="DUPLICATE", source_locator="synthetic")


if __name__ == "__main__":
    unittest.main()
