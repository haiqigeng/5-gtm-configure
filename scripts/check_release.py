#!/usr/bin/env python3
"""Run dependency-free repository and skill release checks."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
CURRENT_RELEASE = "6.1.0"
REFERENCE_LAYERS = {
    "01-orientation": {
        "official-source-policy.md",
        "utility-contract.md",
    },
    "02-execution": {
        "analytics-tags.md",
        "analytics-vendors.md",
        "client-side-object-surface.md",
        "cmp-consent.md",
        "cmp-platform-patterns.md",
        "configuration-contract.md",
        "configuration-run-and-resume.md",
        "conversion-linker-cross-domain.md",
        "data-contract-and-transformations.md",
        "first-party-data.md",
        "ga4-collection-safety.md",
        "google-consent-mode.md",
        "implementation-workflow.md",
        "media-criteo.md",
        "media-affiliate.md",
        "media-floodlight.md",
        "media-google-ads.md",
        "media-linkedin.md",
        "media-meta.md",
        "media-microsoft-ads.md",
        "media-pinterest.md",
        "media-reddit.md",
        "media-snapchat.md",
        "media-tags.md",
        "media-tiktok.md",
        "media-x.md",
        "multi-destination-routing.md",
        "naming-and-reuse.md",
        "template-governance.md",
        "tcf-consent.md",
        "tool-adapters.md",
        "tracking-plan-fidelity-and-conformance.md",
        "transformation-patterns.md",
        "triggers-and-variables.md",
        "vendor-consent-modes.md",
    },
    "03-judgement": {"acceptance-and-handoff.md"},
}
REQUIRED_REFERENCE_FILES = tuple(
    f"references/{layer}/{filename}"
    for layer, filenames in REFERENCE_LAYERS.items()
    for filename in sorted(filenames)
)
REQUIRED_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "pyproject.toml",
    ".gitattributes",
    ".gitignore",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "scripts/check_release.py",
    "scripts/build_skill_package.py",
    "scripts/adapter_runtime.py",
    "scripts/configuration_run.py",
    "scripts/diff_object_graph.py",
    "scripts/validate_configuration_contract.py",
    "scripts/validate_contract_conformance.py",
    "schemas/configuration-run.schema.json",
    "tests/test_adapter_runtime.py",
    "tests/test_configuration_run.py",
    "tests/test_configuration_contract_schema.py",
    "tests/test_cli_json_output.py",
    "tests/test_release.py",
    "tests/test_forward_test_cases.py",
    "tests/test_object_graph_diff.py",
    "tests/test_skill_contract.py",
    "tests/test_configuration_scenarios.py",
    "tests/test_contract_conformance.py",
    "tests/test_utility_scenarios.py",
    "tests/fixtures/configuration_scenarios.json",
    "tests/fixtures/forward_test_cases.json",
    "tests/fixtures/golden_object_graphs.json",
    "tests/fixtures/utility_scenarios.json",
) + REQUIRED_REFERENCE_FILES
STALE_FILES = (
    "references/execution-contract.md",
    "references/official-source-policy.md",
    "references/analytics-tags.md",
    "references/media-tags.md",
    "references/cmp-consent.md",
    "references/naming-and-reuse.md",
    "references/validation-scenarios.md",
    "tests/test_semantic_scenarios.py",
    "tests/fixtures/semantic_scenarios.json",
)
FORBIDDEN_ARTIFACT_NAMES = {"release"}
SCAN_EXCLUDED_NAMES = {
    ".coverage",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "venv",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def parse_frontmatter() -> tuple[str, str]:
    text = read("SKILL.md")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md frontmatter is missing")
    _, raw, _ = text.split("---", 2)
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid frontmatter line: {line}")
        values[key.strip()] = value.strip().strip('"')
    if list(values) != ["name", "description"]:
        raise ValueError("frontmatter must contain only name and description")
    if values.get("name") != "configure-gtm":
        raise ValueError("frontmatter name must be configure-gtm")
    if not values.get("description"):
        raise ValueError("frontmatter description is empty")
    return values["name"], values["description"]


def check_links() -> list[str]:
    errors: list[str] = []
    skill = read("SKILL.md")
    links = re.findall(r"\]\(([^)]+)\)", skill)
    for link in links:
        if link.startswith(("http://", "https://")):
            continue
        if not (ROOT / link).exists():
            errors.append(f"SKILL.md references missing resource: {link}")

    reference_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "references").rglob("*")
        if path.is_file()
    }
    linked_references = {link for link in links if link.startswith("references/")}
    for reference in sorted(reference_files - linked_references):
        errors.append(f"reference is not directly routed from SKILL.md: {reference}")
    for reference in sorted(reference_files):
        text = read(reference)
        if len(text.splitlines()) > 100 and "## Contents" not in text:
            errors.append(f"long reference is missing a Contents section: {reference}")
    return errors


def check_reference_structure() -> list[str]:
    errors: list[str] = []
    references = ROOT / "references"
    actual_layers = {path.name for path in references.iterdir() if path.is_dir()}
    expected_layers = set(REFERENCE_LAYERS)
    for layer in sorted(expected_layers - actual_layers):
        errors.append(f"missing reference layer: references/{layer}")
    for layer in sorted(actual_layers - expected_layers):
        errors.append(f"unexpected reference layer: references/{layer}")

    for layer, expected_files in REFERENCE_LAYERS.items():
        root = references / layer
        if not root.exists():
            continue
        actual_files = {path.name for path in root.iterdir() if path.is_file()}
        for filename in sorted(expected_files - actual_files):
            errors.append(f"missing {layer} reference: {filename}")
        for filename in sorted(actual_files - expected_files):
            errors.append(f"unexpected {layer} reference: {filename}")
        nested = [path for path in root.rglob("*") if path.is_file() and path.parent != root]
        errors.extend(
            f"reference must be directly inside its layer: {path.relative_to(ROOT)}"
            for path in nested
        )

    skill = read("SKILL.md")
    headings = ["## 01 - Orientation", "## 02 - Execution", "## 03 - Judgement"]
    positions = [skill.find(heading) for heading in headings]
    if any(position < 0 for position in positions):
        errors.append("SKILL.md must contain orientation, execution, and judgement headings")
    elif positions != sorted(positions):
        errors.append("SKILL.md reference layers are not ordered orientation/execution/judgement")
    return errors


def check_required_files() -> list[str]:
    errors = [
        f"missing required file: {path}" for path in REQUIRED_FILES if not (ROOT / path).exists()
    ]
    errors.extend(f"stale file remains: {path}" for path in STALE_FILES if (ROOT / path).exists())
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in SCAN_EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.name in FORBIDDEN_ARTIFACT_NAMES:
            errors.append(f"generated artifact must be removed: {relative}")
        if path.suffix in {".pyc", ".pyo"}:
            errors.append(f"generated bytecode must be removed: {relative}")
    return errors


def check_content() -> list[str]:
    errors: list[str] = []
    skill = read("SKILL.md")
    utility = read("references/01-orientation/utility-contract.md")
    sources = read("references/01-orientation/official-source-policy.md")
    configuration_contract = read("references/02-execution/configuration-contract.md")
    configuration_run_reference = read("references/02-execution/configuration-run-and-resume.md")
    fidelity = read("references/02-execution/tracking-plan-fidelity-and-conformance.md")
    workflow = read("references/02-execution/implementation-workflow.md")
    analytics = read("references/02-execution/analytics-tags.md")
    analytics_vendors = read("references/02-execution/analytics-vendors.md")
    object_surface = read("references/02-execution/client-side-object-surface.md")
    media = read("references/02-execution/media-tags.md")
    media_affiliate = read("references/02-execution/media-affiliate.md")
    media_criteo = read("references/02-execution/media-criteo.md")
    media_floodlight = read("references/02-execution/media-floodlight.md")
    media_linkedin = read("references/02-execution/media-linkedin.md")
    media_meta = read("references/02-execution/media-meta.md")
    media_microsoft = read("references/02-execution/media-microsoft-ads.md")
    media_pinterest = read("references/02-execution/media-pinterest.md")
    media_reddit = read("references/02-execution/media-reddit.md")
    media_snap = read("references/02-execution/media-snapchat.md")
    media_tiktok = read("references/02-execution/media-tiktok.md")
    media_x = read("references/02-execution/media-x.md")
    consent = read("references/02-execution/cmp-consent.md")
    cmp_platforms = read("references/02-execution/cmp-platform-patterns.md")
    cross_domain = read("references/02-execution/conversion-linker-cross-domain.md")
    ga4_safety = read("references/02-execution/ga4-collection-safety.md")
    google_consent = read("references/02-execution/google-consent-mode.md")
    vendor_consent = read("references/02-execution/vendor-consent-modes.md")
    routing = read("references/02-execution/multi-destination-routing.md")
    transformations = read("references/02-execution/transformation-patterns.md")
    triggers = read("references/02-execution/triggers-and-variables.md")
    data_contract = read("references/02-execution/data-contract-and-transformations.md")
    first_party_data = read("references/02-execution/first-party-data.md")
    naming = read("references/02-execution/naming-and-reuse.md")
    adapters = read("references/02-execution/tool-adapters.md")
    judgement = read("references/03-judgement/acceptance-and-handoff.md")
    tcf = read("references/02-execution/tcf-consent.md")
    readme = read("README.md")
    changelog = read("CHANGELOG.md")
    contributing = read("CONTRIBUTING.md")
    agent_metadata = read("agents/openai.yaml")
    pyproject = read("pyproject.toml")
    ci_workflow = read(".github/workflows/ci.yml")
    release_workflow = read(".github/workflows/release.yml")
    schema_validator = read("scripts/validate_configuration_contract.py")
    run_controller = read("scripts/configuration_run.py")
    adapter_runtime = read("scripts/adapter_runtime.py")
    graph_diff = read("scripts/diff_object_graph.py")
    run_schema = read("schemas/configuration-run.schema.json")
    compact_skill = " ".join(skill.split())
    compact_utility = " ".join(utility.split())
    compact_configuration_contract = " ".join(configuration_contract.split())
    required_terms = (
        "01 - Orientation",
        "02 - Execution",
        "03 - Judgement",
        "Operationally implement an approved analytics tracking plan",
        "saved, verified GTM object graph",
        "explicit media implementation brief",
        "Default every product to strict/basic CMP blocking",
        "installed template",
        "Inspect only the objects related to the requested implementation",
        "LUT/RLT for deterministic routing",
        "shallow folder",
        "payload-eligibility variables",
        "supported template whenever one exists",
        "greenfield or a delta",
        "configuration-contract.md",
        "never as proof of best practice",
        "never publish",
        "future extensions",
    )
    errors.extend(
        f"SKILL.md missing required term: {term}"
        for term in required_terms
        if term not in compact_skill
    )
    utility_terms = (
        "## Audience",
        "## North star",
        "## Operational quality",
        "## Intake",
        "## Operational output",
        "## Workspace authority",
        "## Boundaries",
    )
    errors.extend(
        f"utility contract missing section: {term}" for term in utility_terms if term not in utility
    )
    contract_terms = (
        "Keep analytics and media business inputs separate",
        "Explicit human media-team brief",
        "Current official vendor browser documentation",
    )
    errors.extend(
        f"utility contract missing requirement authority: {term}"
        for term in contract_terms
        if term not in compact_utility
    )
    configuration_contract_terms = (
        "# Operational configuration map",
        "## Keep business and implementation decisions separate",
        "## Use one concise record per requirement",
        "## Retain critical provenance",
        "`approved-input`",
        "`official-current`",
        "`container-confirmed`",
        "`contract-sample`",
        "## Map fields and runtime data behavior",
        "## Map GTM object actions",
        "## Prove analytics conformance",
        "## Record consent and external dependencies",
        "## Apply canonical acceptance",
        "rename",
        "pause",
        "unpause",
        "A repeated run against the final saved state",
        "payload-eligibility CJS",
    )
    errors.extend(
        f"configuration contract missing requirement: {term}"
        for term in configuration_contract_terms
        if term not in compact_configuration_contract
    )
    configuration_run_terms = (
        "Use one durable run artifact",
        "Preserve stable requirement identity",
        "Render impact without adding a routine approval gate",
        "Checkpoint every write boundary",
        "Resume only from proved state",
        "not retried automatically",
        "Use replace as one governed action",
        "Summarize template permission changes",
        "Hand off in three layers",
        "configuration-run@1.0",
    )
    errors.extend(
        f"configuration-run reference missing requirement: {term}"
        for term in configuration_run_terms
        if term not in configuration_run_reference
    )
    source_terms = (
        "Never rely on memory",
        "never use documentation as permission to substitute",
        "Do not copy an event catalogue into the skill",
        "Microsoft Advertising UET",
        "Microsoft Clarity Consent Mode",
        "TikTok Pixel standard events",
        "Snap Pixel and GTM",
        "Piwik PRO tracking code through GTM",
        "TCF 2.3",
    )
    errors.extend(
        f"official source policy missing contract: {term}"
        for term in source_terms
        if term.casefold() not in sources.casefold()
    )
    workflow_terms = (
        "# Operational implementation workflow",
        "Resolve only blocking inputs",
        "Research the product and installed template",
        "Inspect relevant container integration",
        "Build the configuration map",
        "Design and preflight the object graph",
        "Mutate in dependency order",
        "Read back, correct, and hand off",
        "payload-eligibility helper",
    )
    errors.extend(
        f"workflow missing contract: {term}" for term in workflow_terms if term not in workflow
    )
    capability_contracts = {
        "complete client-side object surface": (
            object_surface,
            (
                "Built-in variables",
                "Google destinations",
                "Zones",
                "Environments",
                "explicit authority",
            ),
        ),
        "GA4 collection safety": (
            ga4_safety,
            ("reserved name", "PII", "hard collection limit", "blocking-error"),
        ),
        "multi-destination routing": (
            routing,
            (
                "safe no-match behavior",
                "Never use a default production destination",
                "static vectors",
            ),
        ),
        "non-GA4 analytics": (
            analytics_vendors,
            ("Matomo", "Piwik PRO", "Adobe", "approved client-side analytics requirement"),
        ),
        "CMP platforms": (
            cmp_platforms,
            ("OneTrust", "Cookiebot", "Didomi", "Common state contract"),
        ),
        "cross-domain architecture": (
            cross_domain,
            ("Conversion Linker", "GA4 Admin", "approved domain"),
        ),
        "transformations": (
            transformations,
            ("Required static vectors", "Preserve original item order", "Forbidden behavior"),
        ),
        "Floodlight": (media_floodlight, ("Floodlight", "Counter", "Sales", "Conversion Linker")),
        "LinkedIn": (media_linkedin, ("LinkedIn Insight Tag", "partner ID", "strict/basic CMP")),
        "Pinterest": (media_pinterest, ("Pinterest Tag", "Tag ID", "strict/basic CMP")),
        "X": (media_x, ("X Pixel", "pixel identity", "strict/basic CMP")),
        "Reddit": (media_reddit, ("Reddit Pixel", "pixel identity", "strict/basic CMP")),
        "Criteo": (media_criteo, ("Criteo OneTag", "page-type", "strict/basic CMP")),
        "Meta": (
            media_meta,
            ("supported installed template", "Keep payload mapping separate from firing"),
        ),
        "Microsoft Advertising": (
            media_microsoft,
            ("supported UET GTM template", "browser UET request"),
        ),
        "TikTok": (
            media_tiktok,
            ("supported TikTok Pixel template", "Avoid automatic and manual duplicates"),
        ),
        "Snap": (
            media_snap,
            ("supported Snap Pixel template", "Conversions API parameter documentation"),
        ),
        "affiliate": (
            media_affiliate,
            ("Affiliate browser tags", "Map conversion and basket fields", "one browser owner"),
        ),
        "TCF": (
            tcf,
            ("TCF 2.3", "Additional Consent", "Configure plumbing, not policy"),
        ),
        "first-party data": (
            first_party_data,
            ("User-Provided Data variable", "not pre-hash it", "account-side activation"),
        ),
    }
    for label, (text, terms) in capability_contracts.items():
        errors.extend(
            f"{label} reference missing contract: {term}" for term in terms if term not in text
        )
    deterministic_contracts = (
        ("configuration schema validator", 'SCHEMA_VERSION = "5.0"', schema_validator),
        ("configuration schema validator", "validate_document", schema_validator),
        ("configuration schema validator", "approved-input", schema_validator),
        ("configuration-run controller", 'SCHEMA_VERSION = "1.0"', run_controller),
        ("configuration-run controller", "checkpoint_operation", run_controller),
        ("configuration-run controller", "reopen_failed_operation", run_controller),
        ("configuration-run controller", "render_markdown", run_controller),
        ("adapter state machine", "collect_paginated", adapter_runtime),
        ("adapter state machine", "AmbiguousWriteError", adapter_runtime),
        ("object graph comparator", "normalize_graph", graph_diff),
        ("object graph comparator", "compare_graphs", graph_diff),
        ("object graph comparator", "extra_objects", graph_diff),
        ("object graph comparator", "REFERENCE_FIELDS", graph_diff),
        ("object graph comparator", "BUILT_IN_TRIGGER_IDS", graph_diff),
        ("object graph comparator", "parentFolderId", graph_diff),
        ("object graph comparator", "setupTag", graph_diff),
    )
    for label, term, text in deterministic_contracts:
        if term not in text:
            errors.append(f"{label} missing contract: {term}")
    analytics_terms = (
        "GA4 - Config",
        "GA4 - Event Setting",
        "send_page_view",
        "Block - <CMP> - GA4 denied",
        "never substitute it automatically",
        "exact approved parameter set",
        "Resolve Google tag and destination identity",
        "`GT-...`",
        "`G-...`",
        "`AW-...`",
        "Use native GA4 ecommerce mechanics",
        "Send Ecommerce data",
        "Reconcile Enhanced Measurement and manual events",
        "`traffic_type`",
        "`debug_mode`",
    )
    errors.extend(
        f"analytics reference missing contract: {term}"
        for term in analytics_terms
        if term not in analytics
    )
    media_terms = (
        "Treat the media brief as the primary business input",
        "dataLayer key",
        "template UI field",
        "current official standard event",
        "multi-item payloads",
        "Use the supported template first",
        "server/CAPI-only fields as excluded",
        "Handle runtime missing data without speculative gates",
    )
    errors.extend(
        f"media reference missing contract: {term}" for term in media_terms if term not in media
    )
    consent_terms = (
        "Default to strict/basic gating",
        "unknown, undefined, uninitialized, and denied state block",
        "every GTM event used by each consumer tag",
        "ignore their own firing and blocking triggers",
        "does not unload a vendor script",
        "Select advanced/native consent only explicitly",
        "documented CMP state variable directly",
    )
    errors.extend(
        f"consent reference missing contract: {term}"
        for term in consent_terms
        if term not in consent
    )
    google_consent_terms = (
        "Basic consent mode",
        "Advanced consent mode",
        "advanced consent-aware",
        "Do not attach a blocking trigger",
        "Google Ads Conversion Tracking and Remarketing",
        "Floodlight",
        "Conversion Linker",
        "analytics_storage",
        "ad_storage",
        "ad_user_data",
        "ad_personalization",
        "unset value can be treated as granted",
        "wait_for_update",
        "ads_data_redaction",
        "url_passthrough",
    )
    errors.extend(
        f"Google consent reference missing contract: {term}"
        for term in google_consent_terms
        if term.lower() not in google_consent.lower()
    )
    vendor_consent_terms = (
        "strict/basic blocked",
        "native stop/hold",
        "native cookie-control",
        "advanced consent-aware",
        "adaptive/anonymous analytics",
        "Google Analytics 4",
        "Google Ads Conversion Tracking and Remarketing",
        "Floodlight",
        "Conversion Linker",
        "Microsoft Advertising UET",
        "Microsoft Clarity",
        "Matomo",
        "Piwik PRO Analytics",
        "TikTok Pixel",
        "classify consent capability only",
        "Discovery baseline last reviewed",
    )
    errors.extend(
        f"vendor consent reference missing contract: {term}"
        for term in vendor_consent_terms
        if term not in vendor_consent
    )
    consent_logic_terms = (
        "logical AND",
        "does not contain <exact documented vendor token>",
        "Do not create a Custom JavaScript",
        "Shared Google execution unit",
        "any matching blocking trigger prevents",
        "smallest reusable set of blocks",
    )
    combined_logic = "\n".join((consent, google_consent, triggers, judgement))
    errors.extend(
        f"consent logic contract missing: {term}"
        for term in consent_logic_terms
        if term.casefold() not in combined_logic.casefold()
    )
    forbidden_consent_logic = (
        "one narrow Boolean variable",
        "one tested Boolean result",
        "separate GA4, Google Ads, and Floodlight blocks even when",
    )
    errors.extend(
        f"obsolete consent implementation remains: {term}"
        for term in forbidden_consent_logic
        if term in combined_logic or term in readme
    )
    judgement_terms = (
        "## Configured means saved and verified",
        "## Operational statuses",
        "## Configuration judgement matrix",
        "## Analytics and consent proof",
        "## Three-layer handoff",
        "Recette cues",
        "Payload map",
        "Same-identity migration cannot be updated",
        "browser event ID",
    )
    errors.extend(
        f"judgement reference missing section: {term}"
        for term in judgement_terms
        if term not in judgement
    )
    trigger_terms = (
        "firing triggers on one tag are alternatives",
        "filter rows within one trigger are cumulative",
        "any matching blocking/exception trigger prevents",
        "Version 1 literal-dot",
        "Version 2 nested-path",
        "priority",
        "custom schedule",
        "live-only behavior",
        "firing option",
        "setup/cleanup references",
        "Just Links",
        "All Elements",
        "Element Visibility",
        "Scroll Depth",
        "YouTube Video",
        "Trigger Group",
    )
    errors.extend(
        f"trigger reference missing semantic: {term}"
        for term in trigger_terms
        if term not in triggers
    )
    adapter_terms = (
        "operational configuration map as the adapter input",
        "current fingerprint",
        "Do not mutate from an informal prose summary",
        "Prove idempotency",
        "synchronize workspace state",
        "Discover exact actions and pagination",
        "Do not guess a generic action alias",
        "Maintain a current-operation journal",
        "scripts/adapter_runtime.py",
        "in_progress",
        "uncertain",
    )
    errors.extend(
        f"tool-adapter reference missing contract: {term}"
        for term in adapter_terms
        if term not in adapters
    )
    fidelity_terms = (
        "measurement design and optimization",
        "Treat these as approved analytics semantics",
        "Treat these as GTM implementation choices",
        "Visibility is evidence, not authority",
        "`blocking-error`",
        "`advisory`",
        "`implementation-note`",
        "scripts/validate_contract_conformance.py",
    )
    errors.extend(
        f"tracking-plan fidelity reference missing contract: {term}"
        for term in fidelity_terms
        if term not in fidelity
    )
    architecture_terms = (
        ("data mapping", "After selecting the target pattern", data_contract),
        ("reuse", "Existing prevalence is not evidence of best", naming),
        ("reuse conflict", "clean parallel implementation", naming),
        (
            "acceptance architecture",
            "Select the best-practice architecture before considering container reuse",
            judgement,
        ),
        ("workspace attribution", "pre-existing workspace changes", judgement),
        ("workspace totals", "final workspace totals", judgement),
    )
    for label, term, text in architecture_terms:
        if term not in text:
            errors.append(f"{label} contract missing: {term}")
    readme_terms = (
        "## Who It Serves",
        "## Utility Objective",
        "## Inputs",
        "## Outputs",
        "## Workflow Architecture",
        "## Boundaries",
        "## Related Skills",
        "## Release Checks",
    )
    errors.extend(f"README missing section: {term}" for term in readme_terms if term not in readme)
    metadata_terms = (
        'display_name: "Configure Google Tag Manager"',
        'default_prompt: "Use $configure-gtm',
    )
    errors.extend(
        f"agents/openai.yaml missing contract: {term}"
        for term in metadata_terms
        if term not in agent_metadata
    )
    short_description = re.search(
        r'^\s+short_description: "(?P<value>[^"]+)"\s*$', agent_metadata, re.M
    )
    if not short_description:
        errors.append("agents/openai.yaml has no quoted short_description")
    elif not 25 <= len(short_description.group("value")) <= 64:
        errors.append("agents/openai.yaml short_description must contain 25-64 characters")
    if not re.search(rf"^## {re.escape(CURRENT_RELEASE)}\s*$", changelog, re.M):
        errors.append("CHANGELOG is missing the current release section")
    expected_tag = f"v{CURRENT_RELEASE}"
    if not re.search(rf'^version = "{re.escape(CURRENT_RELEASE)}"$', pyproject, re.M):
        errors.append("pyproject version does not match CURRENT_RELEASE")
    version_contracts = (
        ("README release check", f"--tag {expected_tag} --release-notes", readme),
        ("README package command", f"configure-gtm-{expected_tag}.zip", readme),
        ("CONTRIBUTING release check", f"--tag {expected_tag} --release-notes", contributing),
        ("CI release check", f"--tag {expected_tag} --release-notes", ci_workflow),
        ("README version policy", "Semantic Versioning: `vMAJOR.MINOR.PATCH`", readme),
        ("release workflow tag filter", '      - "v*.*.*"', release_workflow),
    )
    for label, expected, text in version_contracts:
        if expected not in text:
            errors.append(f"{label} does not match the current release")
    if re.search(r"Scope excludes[^.]*\b(server-side|deduplication)\b", skill, re.I):
        errors.append("server-side/deduplication appears in the permanent exclusion sentence")
    if "future extensions" not in skill.lower():
        errors.append("future capability boundary is not explicit")
    if len(skill.splitlines()) >= 500:
        errors.append("SKILL.md exceeds the 500-line guidance limit")
    release_text = "\n".join(read(path) for path in ("SKILL.md", "README.md", "CHANGELOG.md"))
    if re.search(r"TODO|\[TODO\]", release_text, re.I):
        errors.append("release-facing files contain placeholders")
    runtime_contract = "\n".join(
        read(path)
        for path in (
            "SKILL.md",
            "README.md",
            *(
                path.relative_to(ROOT).as_posix()
                for path in sorted((ROOT / "references").rglob("*.md"))
            ),
        )
    )
    if "Specification complete" in runtime_contract:
        errors.append("obsolete planning-only success status remains in runtime documentation")

    misleading_legacy_phrases = (
        "Use `--allow-legacy` only to read a previously produced v4 contract or an unversioned",
        "v4 authority boundary",
    )
    errors.extend(
        f"stale legacy-contract wording remains: {term}"
        for term in misleading_legacy_phrases
        if term in runtime_contract
    )

    mandatory_runtime_files = (
        "SKILL.md",
        "references/01-orientation/utility-contract.md",
        "references/01-orientation/official-source-policy.md",
        "references/02-execution/implementation-workflow.md",
        "references/02-execution/configuration-contract.md",
        "references/02-execution/configuration-run-and-resume.md",
        "references/03-judgement/acceptance-and-handoff.md",
    )
    mandatory_words = sum(len(re.findall(r"\S+", read(path))) for path in mandatory_runtime_files)
    if mandatory_words > 7500:
        errors.append(f"mandatory runtime instruction load exceeds 7,500 words: {mandatory_words}")

    try:
        parsed_run_schema = json.loads(run_schema)
    except json.JSONDecodeError as exc:
        errors.append(f"configuration-run schema is invalid JSON: {exc}")
    else:
        if parsed_run_schema.get("properties", {}).get("schema_version", {}).get("const") != "1.0":
            errors.append("configuration-run schema does not declare version 1.0")
        if parsed_run_schema.get("additionalProperties") is not False:
            errors.append("configuration-run schema must reject unknown top-level fields")

    if "unversioned comparison inputs cannot authorize mutation" not in schema_validator:
        errors.append("mutation validator does not isolate unversioned comparison input")
    for built_in_id in ("2147479553", "2147479572", "2147479573"):
        if built_in_id not in graph_diff:
            errors.append(f"object graph comparator is missing built-in trigger {built_in_id}")
    return errors


def check_git_release_state(
    tag: str | None, *, require_git_tag: bool, require_clean_tree: bool
) -> list[str]:
    errors: list[str] = []
    if require_clean_tree:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"cannot inspect git worktree: {result.stderr.strip()}")
        elif result.stdout.strip():
            errors.append("release worktree is not clean")

    if require_git_tag:
        if not tag:
            errors.append("--require-git-tag requires --tag")
        else:
            result = subprocess.run(
                ["git", "tag", "--points-at", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                errors.append(f"cannot inspect tags at HEAD: {result.stderr.strip()}")
            elif tag not in result.stdout.splitlines():
                errors.append(f"release tag {tag} does not point at HEAD")
    return errors


def check_release_notes(path: Path) -> list[str]:
    if not path.exists():
        return [f"release notes file does not exist: {path}"]
    text = path.read_text(encoding="utf-8")
    section = re.search(
        rf"^## {re.escape(CURRENT_RELEASE)}\s*$\n(?P<body>.*?)(?=^## |\Z)",
        text,
        re.M | re.S,
    )
    if not section:
        return [f"release notes are missing the {CURRENT_RELEASE} section"]
    text = section.group("body")
    headings = (
        "Why This Release Matters",
        "What Changed",
        "What Users Should Do",
        "Validation",
        "Known Limits",
    )
    return [
        f"release notes missing heading: {heading}"
        for heading in headings
        if f"### {heading}" not in text
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--release-notes", type=Path)
    parser.add_argument("--require-git-tag", action="store_true")
    parser.add_argument("--require-clean-tree", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        _, description = parse_frontmatter()
        if "expert web analyst" not in description.lower():
            errors.append("frontmatter does not identify the expert web analyst audience")
        if len(description) > 1024:
            errors.append("frontmatter description exceeds 1024 characters")
        if "<" in description or ">" in description:
            errors.append("frontmatter description contains a forbidden angle bracket")
    except ValueError as exc:
        errors.append(str(exc))
    errors.extend(check_required_files())
    errors.extend(check_reference_structure())
    errors.extend(check_links())
    errors.extend(check_content())
    if args.tag:
        if not SEMVER.fullmatch(args.tag):
            errors.append(f"invalid Semantic Version release tag: {args.tag}")
        elif args.tag != f"v{CURRENT_RELEASE}":
            errors.append(
                f"release tag {args.tag} does not match current release v{CURRENT_RELEASE}"
            )
    if args.release_notes:
        errors.extend(check_release_notes(args.release_notes))
    errors.extend(
        check_git_release_state(
            args.tag,
            require_git_tag=args.require_git_tag,
            require_clean_tree=args.require_clean_tree,
        )
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Release check: FAIL ({len(errors)} error(s))")
        return 1
    print(
        f"Release check: PASS ({len(REQUIRED_FILES)} required files, {len(read('SKILL.md').splitlines())} SKILL.md lines)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
