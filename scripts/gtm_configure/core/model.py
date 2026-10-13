"""Shared enums and immutable policy constants for configuration run."""

SCHEMA_VERSION = "7.0"
CONTRACT_SCHEMA_VERSION = "9.0"
MATERIALIZATION_METHOD = f"contract-{CONTRACT_SCHEMA_VERSION}-deterministic"
VERIFICATION_SCHEMA_VERSION = "2.0"

RUN_MODES = {"web", "server", "pipeline"}
TARGET_TYPES = {"web", "server"}
EXECUTION_MODES = {"isolated-durable", "refonte-durable"}
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

CONSENT_MODES = {
    "strict-basic",
    "advanced-native",
    "product-specific",
    "client-policy-ungated",
}
TRANSPORT_BEHAVIORS = {"blocked", "always-transported", "conditionally-transported"}
WEB_CONSENT_MECHANISMS = {
    "firing-trigger-condition",
    "additional-consent-checks",
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
    "generated-event-id",
    "template-native",
    "none",
}

SHAPES = {"scalar", "array", "object"}
FIELD_FLOW_STATUSES = {"proved", "blocked", "external"}
PUBLICATION_ORDER = {
    "web": [],
    "server": ["server-recette", "server-publication", "post-publication-smoke"],
    "pipeline": [
        "server-recette",
        "web-pipeline-recette",
        "server-publication",
        "web-cutover-publication",
        "post-publication-smoke",
    ],
}


ROUTES = {"analytics", "media", "consent", "combined", "organization"}

REQUIREMENT_KINDS = {"analytics", "media", "consent", "organization"}

EVIDENCE_GRADES = {
    "approved-input",
    "official-current",
    "container-confirmed",
    "contract-sample",
}


ID_FIELDS = {
    "tagId": "tag",
    "triggerId": "trigger",
    "variableId": "variable",
    "folderId": "folder",
    "templateId": "template",
    "zoneId": "zone",
    "environmentId": "environment",
    "clientId": "client",
    "transformationId": "transformation",
}
BUILT_IN_TRIGGER_IDS = frozenset(
    {
        "2147479553",  # All Pages
        "2147479572",  # Consent Initialization - All Pages
        "2147479573",  # Initialization - All Pages
    }
)
IDENTITY_FIELDS = ("account_id", "container_id", "workspace_id", "container_type")
