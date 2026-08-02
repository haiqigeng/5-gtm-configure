from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


class SkillContractTest(unittest.TestCase):
    def test_openai_interface_metadata_matches_operational_north_star(self) -> None:
        metadata = read("agents/openai.yaml")
        self.assertIn('display_name: "Configure Google Tag Manager"', metadata)
        self.assertIn('short_description: "Complete client-side GTM configuration"', metadata)
        self.assertIn('default_prompt: "Use $configure-gtm', metadata)
        self.assertIn("saved setup", metadata)
        self.assertIn("never publish", metadata)

    def test_entrypoint_defines_saved_object_graph_as_success(self) -> None:
        skill = read("SKILL.md")
        self.assertIn("Operationally implement an approved analytics tracking plan", skill)
        self.assertIn("saved, verified GTM object graph as the unit of success", compact(skill))
        self.assertIn("Create, update, or reuse every required GTM object", compact(skill))
        self.assertNotIn("Specification complete", skill)

    def test_reference_structure_is_orientation_execution_judgement(self) -> None:
        skill = read("SKILL.md")
        headings = ("## 01 - Orientation", "## 02 - Execution", "## 03 - Judgement")
        positions = [skill.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            {path.name for path in (ROOT / "references").iterdir() if path.is_dir()},
            {"01-orientation", "02-execution", "03-judgement"},
        )

    def test_one_internal_workflow_reaches_real_mutation(self) -> None:
        utility = read("references/01-orientation/utility-contract.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        self.assertIn(
            "Do not ask whether the analyst wants read-only, planning, or mutation", utility
        )
        for step in (
            "Resolve only blocking inputs",
            "Create or reuse the workspace",
            "Research the product and installed template",
            "Inspect relevant container integration",
            "Build the configuration map",
            "Design and preflight the object graph",
            "Mutate in dependency order",
            "Read back, correct, and hand off",
        ):
            self.assertIn(step, workflow)

    def test_operational_statuses_prevent_planning_only_success(self) -> None:
        contract = read("references/02-execution/configuration-contract.md")
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        combined = contract + acceptance
        for status in ("Configured", "Partial", "Blocked", "Deferred"):
            self.assertIn(f"`{status}`", acceptance)
        self.assertIn("Apply canonical acceptance", contract)
        self.assertEqual(acceptance.count("## Operational statuses"), 1)
        self.assertNotIn("Specification complete", combined)
        self.assertIn("No planning/specification status substitutes", combined)
        self.assertIn("Authoritative saved-workspace readback", acceptance)

    def test_analytics_and_media_keep_distinct_business_authorities(self) -> None:
        utility = read("references/01-orientation/utility-contract.md")
        self.assertIn("Approved tracking plan or exact direct analytics requirement", utility)
        self.assertIn("Explicit human media-team brief", utility)
        self.assertIn("supporting evidence for a media source event", utility)
        self.assertIn("never copy a GA4 destination name", utility)

    def test_tracking_plan_fidelity_prevents_silent_redesign(self) -> None:
        skill = read("SKILL.md")
        fidelity = read("references/02-execution/tracking-plan-fidelity-and-conformance.md")
        analytics = read("references/02-execution/analytics-tags.md")
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        self.assertIn("Implement approved analytics event names", skill)
        self.assertIn("measurement design and optimization", fidelity)
        self.assertIn("never substitute it automatically", analytics)
        self.assertIn("Valid custom analytics event with a recommended alternative", acceptance)
        self.assertIn("Recommended/optional field absent from plan", acceptance)

    def test_official_documentation_detects_discrepancies_without_authorizing_changes(self) -> None:
        sources = read("references/01-orientation/official-source-policy.md")
        fidelity = read("references/02-execution/tracking-plan-fidelity-and-conformance.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        for term in ("blocking-error", "advisory", "implementation-note"):
            self.assertIn(f"`{term}`", fidelity)
        self.assertIn("never use documentation as permission to substitute", sources.lower())
        self.assertIn("Preserve a technically valid advisory by default", compact(workflow))

    def test_current_official_and_installed_template_evidence_are_mandatory(self) -> None:
        sources = read("references/01-orientation/official-source-policy.md")
        templates = read("references/02-execution/template-governance.md")
        self.assertIn("Never rely on memory", sources)
        self.assertIn("Do not copy an event catalogue into the skill", sources)
        self.assertIn("installed template/version", sources)
        self.assertIn(
            "Confirm that the installed template actually supports every required field", templates
        )
        self.assertIn(
            "If official vendor documentation and the installed template disagree", templates
        )

    def test_configuration_map_is_lightweight_and_exact(self) -> None:
        contract = read("references/02-execution/configuration-contract.md")
        self.assertIn("# Operational configuration map", contract)
        self.assertIn("Keep business and implementation decisions separate", contract)
        self.assertIn("Use one concise record per requirement", contract)
        self.assertIn("Retain critical provenance", contract)
        self.assertIn("Map fields and runtime data behavior", contract)
        self.assertIn("Map GTM object actions", contract)
        self.assertIn("exact outgoing parameter/property/item-field set equality", contract)
        self.assertIn("A repeated run against the final saved state", contract)

    def test_scope_is_relevant_configuration_not_general_audit(self) -> None:
        skill = read("SKILL.md")
        utility = read("references/01-orientation/utility-contract.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        self.assertIn(
            "Inspect only the objects related to the requested implementation",
            compact(skill),
        )
        self.assertIn("does not authorize general cleanup", utility)
        self.assertIn("Inspect only objects that can supply, consume, duplicate", workflow)
        self.assertIn(
            "do not turn the exercise into a tracking-plan or container audit",
            compact(workflow),
        )

    def test_best_practice_architecture_precedes_container_reuse(self) -> None:
        skill = read("SKILL.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        naming = read("references/02-execution/naming-and-reuse.md")
        data = read("references/02-execution/data-contract-and-transformations.md")
        self.assertIn("never as proof of best practice", compact(skill))
        self.assertIn("before evaluating local reuse", workflow)
        self.assertIn("Existing prevalence is not evidence of best", naming)
        self.assertIn("After selecting the target pattern", data)
        self.assertIn("Do not reproduce a legacy pattern", compact(workflow))

    def test_naming_folders_and_advanced_variables_are_deliberate(self) -> None:
        skill = read("SKILL.md")
        naming = read("references/02-execution/naming-and-reuse.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        self.assertIn("Follow the default naming convention", skill)
        self.assertIn("Actively evaluate a LUT/RLT", naming)
        self.assertIn("create or reuse one shallow folder", naming)
        self.assertIn(
            "LUTs or RLTs for real deterministic multi-scenario mappings",
            compact(workflow),
        )
        self.assertIn("narrow Custom JavaScript", skill)

    def test_media_brief_and_official_schema_drive_media_tags(self) -> None:
        media = read("references/02-execution/media-tags.md")
        self.assertIn("Treat the media brief as the primary business input", media)
        self.assertIn("Template UI field", media)
        self.assertIn("current official standard event", media)
        self.assertIn("Do not transform merely because the source uses GA4-style names", media)
        self.assertIn("map every in-scope item rather than selecting item zero", media)
        self.assertIn("Verify the saved media setup", media)

    def test_ecommerce_transformations_preserve_items_without_payload_guards(self) -> None:
        skill = read("SKILL.md")
        data = read("references/02-execution/data-contract-and-transformations.md")
        media = read("references/02-execution/media-tags.md")
        meta = read("references/02-execution/media-meta.md")
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        self.assertIn("Preserve every required ecommerce item", skill)
        self.assertIn("Do not assume that an analytics `item_id`", data)
        self.assertIn("Handle runtime missing data without speculative gates", media)
        self.assertIn("content_ids", meta)
        self.assertIn("contents", meta)
        self.assertIn("Do not assume analytics `item_id` is the Meta catalog ID", meta)
        self.assertIn(
            "runtime missing data as a site/dataLayer and recette dependency",
            compact(acceptance),
        )
        self.assertIn("Do not create `CJS - Meta - ... valid`", meta)
        self.assertIn("Do not create names such as `CJS - Ecommerce - AddToCart Eligible`", data)

    def test_field_resolution_preflight_prevents_destination_source_inference(self) -> None:
        skill = read("SKILL.md")
        contract = read("references/02-execution/configuration-contract.md")
        data = read("references/02-execution/data-contract-and-transformations.md")
        run_script = read("scripts/configuration_run.py")
        self.assertIn("approved actual source and source shape", skill)
        self.assertIn("Never turn a destination or template field name", contract)
        self.assertIn("identically named dataLayer source", data)
        self.assertIn("source_authority_grade", run_script)
        self.assertIn("shape_compatibility", run_script)
        self.assertIn("preflight is incomplete", run_script)

    def test_compound_consent_predicates_use_native_or_denial_graph(self) -> None:
        skill = read("SKILL.md")
        consent = read("references/02-execution/cmp-consent.md")
        triggers = read("references/02-execution/triggers-and-variables.md")
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        self.assertIn("smallest reusable set of CMP blocking/exception triggers", consent)
        self.assertIn("independent required grants each need OR-denial behavior", consent)
        self.assertIn("any matching blocking/exception trigger prevents", triggers)
        self.assertIn("Compound CMP predicate", acceptance)
        self.assertIn("Do not create a Custom JavaScript", consent)
        self.assertIn("strict/basic CMP blocking", skill)

    def test_strict_consent_lifecycle_remains_complete(self) -> None:
        skill = read("SKILL.md")
        consent = read("references/02-execution/cmp-consent.md")
        triggers = read("references/02-execution/triggers-and-variables.md")
        self.assertIn("every in-scope vendor base/configuration and event tag", skill)
        self.assertIn("it does not replace the reusable vendor block", consent)
        self.assertIn("default to a tested `.*` regex matcher", triggers)
        for term in (
            "Default to strict/basic gating",
            "unknown, undefined, uninitialized, and denied state block",
            "does not retry automatically",
            "every GTM event used by each consumer tag",
            "ignore their own firing and blocking triggers",
            "does not unload a vendor script",
            "logical AND",
            "documented CMP state variable directly",
        ):
            self.assertIn(term, consent)

    def test_advanced_consent_is_product_specific_and_explicit(self) -> None:
        registry = read("references/02-execution/vendor-consent-modes.md")
        google = read("references/02-execution/google-consent-mode.md")
        self.assertIn("per browser product, not only per vendor", registry)
        for route in (
            "strict/basic blocked",
            "native stop/hold",
            "native cookie-control",
            "advanced consent-aware",
            "adaptive/anonymous analytics",
        ):
            self.assertIn(route, registry)
        self.assertIn("Use advanced behavior only when the analyst explicitly requests", google)
        self.assertIn("does not execute runtime recette", google)

    def test_google_shared_execution_units_cannot_mix_routes(self) -> None:
        google = read("references/02-execution/google-consent-mode.md")
        analytics = read("references/02-execution/analytics-tags.md")
        google_ads = read("references/02-execution/media-google-ads.md")
        self.assertIn("blocks that tag for every connected destination", google)
        self.assertIn("officially supported destination-specific separation", google)
        self.assertIn("shared Google tag destinations", analytics)
        self.assertIn("shared with GA4", google_ads)

    def test_trigger_pageview_and_advanced_settings_are_explicit(self) -> None:
        triggers = read("references/02-execution/triggers-and-variables.md")
        analytics = read("references/02-execution/analytics-tags.md")
        media = read("references/02-execution/media-tags.md")
        for term in (
            "firing triggers on one tag are alternatives",
            "filter rows within one trigger are cumulative",
            "Version 1 literal-dot",
            "Version 2 nested-path",
            "priority",
            "custom schedule",
            "firing option",
        ):
            self.assertIn(term, triggers)
        self.assertIn("Keep page view separate by default", analytics)
        self.assertIn("Do not make a base/configuration tag send a page view by default", media)

    def test_every_new_object_requires_a_current_justification(self) -> None:
        skill = read("SKILL.md")
        workflow = read("references/02-execution/implementation-workflow.md")
        contract = read("references/02-execution/configuration-contract.md")
        self.assertIn("Build the smallest understandable object graph", skill)
        self.assertIn("Justify every create or update", workflow)
        self.assertIn("requirement or documented constraint that justifies", contract)

    def test_adapter_contract_mutates_safely_and_is_idempotent(self) -> None:
        adapters = read("references/02-execution/tool-adapters.md")
        self.assertIn("operational configuration map as the adapter input", adapters)
        self.assertIn("current fingerprint", adapters)
        self.assertIn("complete pre-change representation", adapters)
        self.assertIn("Discover exact actions and pagination", adapters)
        self.assertIn("Do not guess a generic action alias", adapters)
        self.assertIn("Maintain a current-operation journal", adapters)
        self.assertIn("Prove idempotency", adapters)
        self.assertIn("Stop when mutation is unavailable", adapters)
        self.assertIn("mark the affected requirement `Blocked`", adapters)

    def test_handoff_separates_workspace_state_and_never_publishes(self) -> None:
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        adapters = read("references/02-execution/tool-adapters.md")
        for text in (acceptance, adapters):
            self.assertIn("pre-existing workspace changes", text)
            self.assertIn("current-run", text)
            self.assertIn("final workspace totals", text)
        self.assertIn(
            "no runtime recette, publication, Submit, or GTM",
            compact(acceptance),
        )

    def test_external_administration_is_not_silently_claimed(self) -> None:
        analytics = read("references/02-execution/analytics-tags.md")
        media = read("references/02-execution/media-tags.md")
        self.assertIn("Record external Google and GA4 administration", analytics)
        self.assertIn("custom dimensions or metrics", analytics)
        self.assertIn("key-event designation", analytics)
        self.assertIn("Record external platform dependencies", media)
        self.assertIn("conversion actions", media)
        self.assertIn("Sending a browser event never proves", media)

    def test_priority_media_playbooks_exist_and_route_from_skill(self) -> None:
        skill = read("SKILL.md")
        for platform in (
            "media-criteo.md",
            "media-floodlight.md",
            "media-google-ads.md",
            "media-linkedin.md",
            "media-microsoft-ads.md",
            "media-meta.md",
            "media-pinterest.md",
            "media-reddit.md",
            "media-tiktok.md",
            "media-snapchat.md",
            "media-x.md",
            "media-affiliate.md",
        ):
            self.assertIn(platform, skill)
            self.assertTrue((ROOT / "references" / "02-execution" / platform).exists())

    def test_complete_client_side_object_surface_is_supported_and_risk_gated(self) -> None:
        skill = read("SKILL.md")
        surface = read("references/02-execution/client-side-object-surface.md")
        adapters = read("references/02-execution/tool-adapters.md")
        for term in (
            "Built-in variables",
            "Google destinations",
            "Zones",
            "Environments",
            "Container settings",
        ):
            self.assertIn(term, surface)
        self.assertIn("explicit authority", surface)
        self.assertIn("object-family coverage", skill.lower())
        self.assertIn("capability independently for workspace", adapters)

    def test_ga4_safety_and_multi_destination_routing_fail_closed(self) -> None:
        safety = read("references/02-execution/ga4-collection-safety.md")
        routing = read("references/02-execution/multi-destination-routing.md")
        for term in ("reserved name", "hard collection limit", "PII", "blocking-error"):
            self.assertIn(term, safety)
        self.assertIn("safe no-match behavior", routing)
        self.assertIn("Never use a default production destination", routing)
        self.assertIn("static vectors", routing)

    def test_non_ga4_analytics_cmp_and_cross_domain_routes_are_first_class(self) -> None:
        skill = read("SKILL.md")
        analytics_vendors = read("references/02-execution/analytics-vendors.md")
        cmp_platforms = read("references/02-execution/cmp-platform-patterns.md")
        cross_domain = read("references/02-execution/conversion-linker-cross-domain.md")
        for routed in (
            "analytics-vendors.md",
            "cmp-platform-patterns.md",
            "conversion-linker-cross-domain.md",
        ):
            self.assertIn(routed, skill)
        for vendor in ("Matomo", "Piwik PRO", "Adobe"):
            self.assertIn(vendor, analytics_vendors)
        for cmp in ("OneTrust", "Didomi", "Axeptio"):
            self.assertIn(cmp, cmp_platforms)
            self.assertIn(f"## {cmp}", cmp_platforms)
        for secondary_cmp in (
            "Cookiebot",
            "Commanders Act/TrustCommander",
            "Usercentrics",
            "Quantcast",
        ):
            self.assertIn(secondary_cmp, cmp_platforms)
        self.assertNotIn("## Cookiebot", cmp_platforms)
        self.assertIn("axeptio_authorized", cmp_platforms.lower())
        self.assertIn("support.axeptio.eu", cmp_platforms)
        self.assertIn("Conversion Linker", cross_domain)
        self.assertIn("GA4 Admin", cross_domain)

    def test_versioned_contract_and_object_graph_diff_are_runtime_controls(self) -> None:
        contract = read("references/02-execution/configuration-contract.md")
        validator = read("scripts/validate_configuration_contract.py")
        graph_diff = read("scripts/diff_object_graph.py")
        package = read("scripts/build_skill_package.py")
        self.assertIn('"schema_version": "5.0"', contract)
        self.assertIn('SCHEMA_VERSION = "5.0"', validator)
        self.assertIn("approved-input", validator)
        self.assertIn("compare_graphs", graph_diff)
        self.assertIn('"scripts/validate_configuration_contract.py"', package)
        self.assertIn('"scripts/diff_object_graph.py"', package)
        self.assertIn('"scripts/configuration_run.py"', package)
        self.assertIn('"scripts/adapter_runtime.py"', package)
        self.assertIn('"schemas"', package)

    def test_runtime_run_contract_is_routed_without_instruction_bloat(self) -> None:
        skill = read("SKILL.md")
        run_reference = read("references/02-execution/configuration-run-and-resume.md")
        run_script = read("scripts/configuration_run.py")
        adapter_runtime = read("scripts/adapter_runtime.py")
        self.assertIn("configuration-run-and-resume.md", skill)
        self.assertIn("configuration-run schema", skill)
        for term in (
            "Use one durable run artifact",
            "Checkpoint every write boundary",
            "Resume only from proved state",
            "not retried automatically",
            "Hand off in three layers",
        ):
            self.assertIn(term, run_reference)
        self.assertRegex(run_script, r'(?m)^SCHEMA_VERSION = "1\.1"$')
        self.assertIn("reopen_failed_operation", run_script)
        self.assertIn("collect_paginated", adapter_runtime)
        mandatory = (
            "SKILL.md",
            "references/01-orientation/utility-contract.md",
            "references/01-orientation/official-source-policy.md",
            "references/02-execution/implementation-workflow.md",
            "references/02-execution/configuration-contract.md",
            "references/02-execution/configuration-run-and-resume.md",
            "references/03-judgement/acceptance-and-handoff.md",
        )
        word_count = sum(len(read(path).split()) for path in mandatory)
        self.assertLessEqual(word_count, 7500)

    def test_user_data_runtime_and_future_boundaries_remain_guarded(self) -> None:
        user_data = read("references/02-execution/first-party-data.md")
        data = read("references/02-execution/data-contract-and-transformations.md")
        utility = read("references/01-orientation/utility-contract.md")
        self.assertIn("Do not enable automatic or manual collection by default", user_data)
        self.assertIn("does not authorize attaching it to every event", user_data)
        self.assertIn("Configure it directly on that Google tag", user_data)
        self.assertIn("unrelated tags and events do not inherit", user_data)
        self.assertIn("Never generate a browser/server event ID", data)
        self.assertIn("execute GTM Preview", utility)
        self.assertIn("never publish", utility.lower())
        self.assertIn("future extensions", utility)

    def test_native_ga4_and_google_identity_mechanics_are_operational(self) -> None:
        analytics = read("references/02-execution/analytics-tags.md")
        for term in (
            "Resolve Google tag and destination identity",
            "`GT-...`",
            "`G-...`",
            "`AW-...`",
            "Use native GA4 ecommerce mechanics",
            "Send Ecommerce data",
            "Reconcile Enhanced Measurement and manual events",
            "send `null`",
            "`traffic_type`",
            "`debug_mode`",
        ):
            self.assertIn(term, analytics)

    def test_template_first_and_browser_server_field_boundary_are_enforced(self) -> None:
        skill = read("SKILL.md")
        templates = read("references/02-execution/template-governance.md")
        media = read("references/02-execution/media-tags.md")
        self.assertIn("supported template whenever one exists", skill)
        self.assertIn("Custom HTML is not a permission bypass", templates)
        self.assertIn("server/CAPI-only fields as excluded", media)
        self.assertIn("supported template field", media)

    def test_google_consent_tcf_and_first_party_data_routes_are_complete(self) -> None:
        google = read("references/02-execution/google-consent-mode.md")
        tcf = read("references/02-execution/tcf-consent.md")
        user_data = read("references/02-execution/first-party-data.md")
        for signal in (
            "analytics_storage",
            "ad_storage",
            "ad_user_data",
            "ad_personalization",
        ):
            self.assertIn(signal, google)
        self.assertIn("unset value can be treated as granted", google)
        for option in (
            "`region`",
            "`wait_for_update`",
            "`ads_data_redaction`",
            "`url_passthrough`",
        ):
            self.assertIn(option, google)
        self.assertIn("TCF 2.3", tcf)
        self.assertIn("Additional Consent", tcf)
        self.assertIn("User-Provided Data variable", user_data)
        self.assertIn("not pre-hash it", compact(user_data))

    def test_delta_and_recette_ready_handoff_are_explicit(self) -> None:
        skill = read("SKILL.md")
        contract = read("references/02-execution/configuration-contract.md")
        acceptance = read("references/03-judgement/acceptance-and-handoff.md")
        for action in ("rename", "pause", "unpause"):
            self.assertIn(action, contract)
        self.assertIn("Classify the request as greenfield or a delta", skill)
        self.assertIn("Recette cues", acceptance)
        self.assertIn("Payload map", acceptance)


if __name__ == "__main__":
    unittest.main()
