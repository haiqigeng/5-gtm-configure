"""Shared enums and immutable policy constants for configuration-run@4.0."""

SCHEMA_VERSION = "4.0"
CONTRACT_SCHEMA_VERSION = "7.0"
VERIFICATION_SCHEMA_VERSION = "1.0"

RUN_MODES = {"web", "server", "pipeline"}
TARGET_TYPES = {"web", "server"}
EXECUTION_MODES = {"isolated-lightweight", "isolated-durable", "refonte-durable"}
RUN_PHASES = {"preflight", "mutation", "readback", "complete"}
RUN_STATUSES = {"In progress", "Configured", "Partial", "Blocked", "Deferred"}
REQUIREMENT_STATUSES = RUN_STATUSES.copy()
TARGET_STATUSES = RUN_STATUSES.copy()
OPERATION_STATES = {
    "planned",
    "in_progress",
    "saved",
    "verified",
    "failed",
    "uncertain",
    "skipped",
}
ALLOWED_TRANSITIONS = {
    "planned": {"in_progress", "skipped", "verified", "failed"},
    "in_progress": {"saved", "verified", "failed", "uncertain"},
    "saved": {"verified", "failed", "uncertain"},
    "uncertain": {"verified", "failed"},
    "verified": set(),
    "failed": set(),
    "skipped": set(),
}

WEB_RESOURCE_FAMILIES = {
    "built-in variable",
    "container setting",
    "destination",
    "environment",
    "folder",
    "google tag configuration",
    "tag",
    "template",
    "trigger",
    "variable",
    "workspace",
    "zone",
}
SERVER_RESOURCE_FAMILIES = {
    "client",
    "container setting",
    "folder",
    "tag",
    "template",
    "transformation",
    "trigger",
    "variable",
    "workspace",
}
RESOURCE_FAMILIES = WEB_RESOURCE_FAMILIES | SERVER_RESOURCE_FAMILIES

ACTIONS = {
    "create",
    "update",
    "replace",
    "rename",
    "pause",
    "unpause",
    "reuse",
    "untouched",
    "remove",
}
DELTA_ACTIONS = {"update", "replace", "rename", "pause", "unpause", "remove"}
MUTATING_ACTIONS = {"create", *DELTA_ACTIONS}
HIGH_IMPACT_ACTIONS = {"replace", "pause", "unpause", "remove"}
AUTHORITY_GRADES = {"approved-input", "official-current", "container-confirmed"}

CONSENT_MODES = {"strict-basic", "advanced-native", "product-specific"}
TRANSPORT_BEHAVIORS = {"blocked", "always-transported", "conditionally-transported"}
WEB_CONSENT_MECHANISMS = {
    "cmp-lifecycle-plus-vendor-block",
    "business-trigger-plus-vendor-block",
    "transport-trigger-only",
    "google-consent-mode",
    "product-native",
    "none",
    "not-applicable",
}
SERVER_CONSENT_MECHANISMS = {
    "incoming-google-consent-native",
    "server-template-native-consent",
    "server-additional-consent-check",
    "server-blocking-trigger",
    "none",
}
UNKNOWN_STATE_BEHAVIORS = {"deny", "native-product-behavior", "explicit-policy"}
CONSENT_SIGNAL_AUTHORITIES = {
    "google-consent-mode",
    "third-party-cmp",
    "product-native",
    "none",
}

DEDUP_STRATEGIES = {
    "single-channel",
    "server-replaces-browser",
    "dual-shared-id",
    "platform-native",
    "not-applicable",
}
DEDUP_SOURCE_TYPES = {
    "transaction-id",
    "stable-occurrence-id",
    "approved-event-id",
    "template-native",
    "none",
}

SHAPES = {"scalar", "array", "object"}
FIELD_FLOW_STATUSES = {"proved", "blocked", "external"}
PUBLICATION_DEPENDENCY_KINDS = {
    "server-publication",
    "server-recette",
    "web-cutover-publication",
    "web-pipeline-recette",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "run",
    "requirements",
    "pipelines",
    "object_changes",
    "payload_mappings",
    "consent_topologies",
    "execution_topologies",
    "page_view_decisions",
    "first_party_data_routes",
    "inventory_dispositions",
    "container_baselines",
    "dedup_contracts",
    "saved_readback",
    "target_results",
    "official_sources",
    "external_dependencies",
    "publication_dependencies",
    "recovery_boundary",
    "idempotency",
}
