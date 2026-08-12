from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
    validate_document,
)


def valid_contract() -> dict:
    return {
        "schema_version": "5.0",
        "route": "analytics",
        "scope": {"included": ["REQ-1"], "reference_only": [], "excluded": []},
        "requirements": [
            {
                "id": "REQ-1",
                "authority": {
                    "grade": "approved-input",
                    "locator": "Tracking Plan / row 1",
                },
                "event_name": "generate_lead",
                "source_event": "form_success",
                "parameters": {
                    "method": {
                        "source": "event.method",
                        "source_shape": "scalar:string",
                        "destination_shape": "scalar:string",
                        "provenance": {
                            "grade": "approved-input",
                            "locator": "Tracking Plan / row 1 / method",
                        },
                    }
                },
            }
        ],
        "implementation": {
            "workspace": {
                "account_id": "account-1",
                "container_id": "container-1",
                "id": "workspace-1",
                "container_type": "web",
            },
            "objects": [
                {
                    "action": "create",
                    "object_type": "tag",
                    "name": "GA4 - Event - generate_lead",
                    "justification": "Implements REQ-1 exactly",
                    "evidence": [
                        "approved-input",
                        "official-current",
                        "container-confirmed",
                    ],
                }
            ],
        },
        "evidence": [
            {
                "grade": "official-current",
                "locator": "GA4 event reference",
                "url": "https://developers.google.com/example",
                "title": "GA4 reference",
                "access_date": "2026-07-21",
            },
            {
                "grade": "container-confirmed",
                "locator": "account/container/workspace IDs",
            },
        ],
        "external_dependencies": [],
    }


class ConfigurationContractSchemaTest(unittest.TestCase):
    def test_valid_v5_contract_passes(self) -> None:
        self.assertEqual(validate_document(valid_contract())["schema_version"], "5.0")

    def test_current_contract_requires_canonical_object_resource_family(self) -> None:
        contract = valid_contract()
        contract["implementation"]["objects"][0]["object_type"] = "Google tag"
        with self.assertRaisesRegex(ContractValidationError, "canonical GTM resource family"):
            validate_document(contract)

    def test_analytics_field_requires_approved_provenance(self) -> None:
        contract = valid_contract()
        contract["requirements"][0]["parameters"]["method"]["provenance"]["grade"] = (
            "official-current"
        )
        with self.assertRaisesRegex(ContractValidationError, "approved-input"):
            validate_document(contract)

    def test_implementation_key_cannot_enter_requirement(self) -> None:
        contract = valid_contract()
        contract["requirements"][0]["gtm_variable"] = "DLV - event.method"
        with self.assertRaisesRegex(ContractValidationError, "implementation-only"):
            validate_document(contract)

    def test_parameter_without_locator_fails(self) -> None:
        contract = valid_contract()
        del contract["requirements"][0]["parameters"]["method"]["provenance"]["locator"]
        with self.assertRaisesRegex(ContractValidationError, "locator"):
            validate_document(contract)

    def test_field_shapes_are_required_before_mapping(self) -> None:
        for missing in ("source_shape", "destination_shape"):
            with self.subTest(missing=missing):
                contract = valid_contract()
                del contract["requirements"][0]["parameters"]["method"][missing]
                with self.assertRaisesRegex(ContractValidationError, missing):
                    validate_document(contract)

    def test_media_source_needs_separate_approved_authority(self) -> None:
        contract = valid_contract()
        contract["route"] = "media"
        field = contract["requirements"][0]["parameters"]["method"]
        field["provenance"]["grade"] = "official-current"
        with self.assertRaisesRegex(ContractValidationError, "source_authority"):
            validate_document(contract)

        field["source_authority"] = {
            "grade": "approved-input",
            "locator": "Media brief / method source",
        }
        self.assertEqual(validate_document(contract)["route"], "media")

    def test_destination_field_can_remain_blocked_without_an_invented_source(self) -> None:
        contract = valid_contract()
        field = contract["requirements"][0]["parameters"]["method"]
        del field["source"]
        del field["source_shape"]
        self.assertEqual(validate_document(contract)["schema_version"], "5.0")

    def test_high_impact_action_requires_explicit_authority(self) -> None:
        for object_type in (
            "zone",
            "destination",
            "container setting",
            "google tag configuration",
            "template",
        ):
            with self.subTest(object_type=object_type):
                contract = valid_contract()
                contract["implementation"]["objects"][0]["object_type"] = object_type
                with self.assertRaisesRegex(ContractValidationError, "explicit_authority"):
                    validate_document(contract)

    def test_update_requires_pre_change_state(self) -> None:
        contract = valid_contract()
        contract["implementation"]["objects"][0]["action"] = "update"
        with self.assertRaisesRegex(ContractValidationError, "pre_change"):
            validate_document(contract)

        contract = valid_contract()
        item = contract["implementation"]["objects"][0]
        item["action"] = "update"
        item["pre_change"] = None
        with self.assertRaisesRegex(ContractValidationError, "must be an object"):
            validate_document(contract)

        contract = valid_contract()
        item = contract["implementation"]["objects"][0]
        item["action"] = "update"
        item["pre_change"] = {}
        with self.assertRaisesRegex(ContractValidationError, "must not be empty"):
            validate_document(contract)

    def test_delta_actions_require_pre_change_and_rename_target(self) -> None:
        for action in ("rename", "pause", "unpause"):
            with self.subTest(action=action):
                contract = valid_contract()
                contract["implementation"]["objects"][0]["action"] = action
                if action == "rename":
                    contract["implementation"]["objects"][0]["new_name"] = "Renamed object"
                with self.assertRaisesRegex(ContractValidationError, "pre_change"):
                    validate_document(contract)

        contract = valid_contract()
        item = contract["implementation"]["objects"][0]
        item["action"] = "rename"
        item["pre_change"] = {"name": item["name"]}
        with self.assertRaisesRegex(ContractValidationError, "new_name"):
            validate_document(contract)

        for action in ("rename", "pause", "unpause"):
            with self.subTest(valid_action=action):
                contract = valid_contract()
                item = contract["implementation"]["objects"][0]
                item["action"] = action
                item["pre_change"] = {"paused": action == "unpause", "name": item["name"]}
                if action == "rename":
                    item["new_name"] = "Renamed object"
                self.assertEqual(validate_document(contract)["schema_version"], "5.0")

        for action in ("pause", "unpause"):
            with self.subTest(incompatible_action=action):
                contract = valid_contract()
                item = contract["implementation"]["objects"][0]
                item.update(
                    {
                        "action": action,
                        "object_type": "variable",
                        "pre_change": {"name": item["name"], "type": "c"},
                    }
                )
                with self.assertRaisesRegex(ContractValidationError, "only for tag"):
                    validate_document(contract)

    def test_remove_requires_pre_change_and_destructive_authority(self) -> None:
        contract = valid_contract()
        item = contract["implementation"]["objects"][0]
        item["action"] = "remove"
        item["destructive_authorization"] = True
        with self.assertRaisesRegex(ContractValidationError, "pre_change"):
            validate_document(contract)

        item["pre_change"] = {"name": item["name"], "tagId": "81"}
        self.assertEqual(validate_document(contract)["schema_version"], "5.0")

    def test_replace_is_one_governed_existing_object_action(self) -> None:
        contract = valid_contract()
        item = contract["implementation"]["objects"][0]
        item.update(
            {
                "action": "replace",
                "object_id": "81",
                "pre_change": {"name": item["name"], "tagId": "81", "type": "legacy"},
                "intended": {"name": item["name"], "type": "gaawe"},
                "replacement_reason": "The adapter cannot express the approved type migration as an update.",
                "destructive_authorization": True,
            }
        )
        self.assertEqual(validate_document(contract)["schema_version"], "5.0")

        for missing in (
            "object_id",
            "pre_change",
            "intended",
            "replacement_reason",
            "destructive_authorization",
        ):
            with self.subTest(missing=missing):
                invalid = deepcopy(contract)
                del invalid["implementation"]["objects"][0][missing]
                with self.assertRaises(ContractValidationError):
                    validate_document(invalid)

    def test_object_requirement_links_must_reference_included_ids(self) -> None:
        contract = valid_contract()
        contract["implementation"]["objects"][0]["requirement_ids"] = ["REQ-1"]
        self.assertEqual(validate_document(contract)["schema_version"], "5.0")

        contract["implementation"]["objects"][0]["requirement_ids"] = ["REQ-99"]
        with self.assertRaisesRegex(ContractValidationError, "unknown requirement IDs"):
            validate_document(contract)

    def test_duplicate_and_contradictory_object_actions_fail(self) -> None:
        duplicate_create = valid_contract()
        duplicate_create["implementation"]["objects"].append(
            deepcopy(duplicate_create["implementation"]["objects"][0])
        )
        with self.assertRaisesRegex(ContractValidationError, "duplicate or contradictory"):
            validate_document(duplicate_create)

        create_and_update = valid_contract()
        update = deepcopy(create_and_update["implementation"]["objects"][0])
        update["action"] = "update"
        update["pre_change"] = {"name": update["name"], "tagId": "81"}
        create_and_update["implementation"]["objects"].append(update)
        with self.assertRaisesRegex(ContractValidationError, "duplicate or contradictory"):
            validate_document(create_and_update)

    def test_rename_target_cannot_collide_with_another_object_action(self) -> None:
        contract = valid_contract()
        renamed = contract["implementation"]["objects"][0]
        renamed["action"] = "rename"
        renamed["pre_change"] = {"name": renamed["name"], "tagId": "81"}
        renamed["new_name"] = "GA4 - Event - qualified_lead"
        other = deepcopy(renamed)
        other["action"] = "create"
        other["name"] = renamed["new_name"]
        other.pop("pre_change")
        other.pop("new_name")
        contract["implementation"]["objects"].append(other)
        with self.assertRaisesRegex(ContractValidationError, "duplicate or contradictory"):
            validate_document(contract)

    def test_object_action_evidence_must_support_the_action(self) -> None:
        sample_only = valid_contract()
        sample_only["implementation"]["objects"][0]["evidence"] = ["contract-sample"]
        with self.assertRaisesRegex(ContractValidationError, "sole action evidence"):
            validate_document(sample_only)

        unauthorised_create = valid_contract()
        unauthorised_create["implementation"]["objects"][0]["evidence"] = ["container-confirmed"]
        with self.assertRaisesRegex(ContractValidationError, "approved-input.*official-current"):
            validate_document(unauthorised_create)

        unconfirmed_reuse = valid_contract()
        unconfirmed_reuse["implementation"]["objects"][0]["action"] = "reuse"
        unconfirmed_reuse["implementation"]["objects"][0]["evidence"] = ["approved-input"]
        with self.assertRaisesRegex(ContractValidationError, "container-confirmed"):
            validate_document(unconfirmed_reuse)

    def test_scope_and_requirement_ids_must_match(self) -> None:
        contract = valid_contract()
        contract["scope"]["included"] = ["REQ-2"]
        with self.assertRaisesRegex(ContractValidationError, "must equal"):
            validate_document(contract)

    def test_scope_partitions_must_be_present_and_disjoint(self) -> None:
        contract = valid_contract()
        del contract["scope"]["excluded"]
        with self.assertRaisesRegex(ContractValidationError, "scope.excluded"):
            validate_document(contract)

        contract = valid_contract()
        contract["scope"]["excluded"] = ["REQ-1"]
        with self.assertRaisesRegex(ContractValidationError, "overlap"):
            validate_document(contract)

    def test_target_must_be_a_stable_web_workspace(self) -> None:
        contract = valid_contract()
        contract["implementation"]["workspace"]["container_type"] = "server"
        with self.assertRaisesRegex(ContractValidationError, "must be 'web'"):
            validate_document(contract)

    def test_official_evidence_requires_https_and_iso_date(self) -> None:
        contract = valid_contract()
        contract["evidence"][0]["url"] = "http://developers.google.com/example"
        with self.assertRaisesRegex(ContractValidationError, "HTTPS"):
            validate_document(contract)

        contract = valid_contract()
        contract["evidence"][0]["access_date"] = "21/07/2026"
        with self.assertRaisesRegex(ContractValidationError, "YYYY-MM-DD"):
            validate_document(contract)

    def test_combined_route_applies_authority_per_requirement_kind(self) -> None:
        analytics = valid_contract()
        analytics["route"] = "combined"
        analytics["requirements"][0]["kind"] = "analytics"
        analytics["requirements"][0]["parameters"]["method"]["provenance"]["grade"] = (
            "official-current"
        )
        with self.assertRaisesRegex(ContractValidationError, "approved-input"):
            validate_document(analytics)

        media = valid_contract()
        media["route"] = "combined"
        media["requirements"][0]["kind"] = "media"
        media_field = media["requirements"][0]["parameters"]["method"]
        media_field["provenance"]["grade"] = "official-current"
        media_field["source_authority"] = {
            "grade": "approved-input",
            "locator": "Media brief / method source",
        }
        self.assertEqual(validate_document(media)["route"], "combined")

    def test_combined_route_requires_requirement_kind(self) -> None:
        contract = valid_contract()
        contract["route"] = "combined"
        with self.assertRaisesRegex(ContractValidationError, "kind"):
            validate_document(contract)

    def test_v4_contract_is_only_allowed_explicitly(self) -> None:
        legacy = valid_contract()
        legacy["schema_version"] = "4.0"
        legacy_field = legacy["requirements"][0]["parameters"]["method"]
        del legacy_field["source_shape"]
        del legacy_field["destination_shape"]
        item = legacy["implementation"]["objects"][0]
        item["object_type"] = "Google tag"
        item["evidence"] = ["container-confirmed"]
        historical_template = deepcopy(item)
        historical_template["object_type"] = "template"
        historical_template["name"] = "Historical custom template"
        legacy["implementation"]["objects"].append(historical_template)

        with self.assertRaisesRegex(ContractValidationError, "is legacy"):
            validate_document(legacy)
        self.assertEqual(
            validate_document(deepcopy(legacy), allow_legacy=True)["schema_version"],
            "4.0",
        )

    def test_unversioned_input_never_enters_mutation_validator(self) -> None:
        legacy = {"scope": {"included": ["REQ-1"]}, "requirements": [{"id": "REQ-1"}]}
        with self.assertRaisesRegex(ContractValidationError, "schema_version"):
            validate_document(legacy)
        with self.assertRaisesRegex(ContractValidationError, "cannot authorize mutation"):
            validate_document(deepcopy(legacy), allow_legacy=True)


if __name__ == "__main__":
    unittest.main()
