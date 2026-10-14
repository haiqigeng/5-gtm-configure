"""Shared enums and immutable policy constants for configuration run."""

from gtm_configure.core.schemas import schema_enum

SCHEMA_VERSION = "9.0"
CONTRACT_SCHEMA_VERSION = "11.0"
MATERIALIZATION_METHOD = f"contract-{CONTRACT_SCHEMA_VERSION}-deterministic"
VERIFICATION_SCHEMA_VERSION = "2.0"

RUN_MODES = schema_enum("run", "$defs", "run", "properties", "mode")
TARGET_TYPES = schema_enum(
    "common",
    "$defs",
    "baselineCapture",
    "properties",
    "source_identity",
    "properties",
    "container_type",
)
EXECUTION_MODES = schema_enum("run", "$defs", "run", "properties", "execution_mode")
RUN_PHASES = schema_enum("run", "$defs", "run", "properties", "phase")
RUN_STATUSES = schema_enum("run", "$defs", "status")
REQUIREMENT_STATUSES = RUN_STATUSES.copy()
TARGET_STATUSES = RUN_STATUSES.copy()
OPERATION_STATES = schema_enum("run", "$defs", "operation", "properties", "state")
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

ACTIONS = schema_enum("run", "$defs", "operation", "properties", "action")
DELTA_ACTIONS = {"update", "replace", "rename", "pause", "unpause", "remove"}
MUTATING_ACTIONS = {"create", *DELTA_ACTIONS}
HIGH_IMPACT_ACTIONS = {"replace", "pause", "unpause", "remove"}

CONSENT_MODES = schema_enum("common", "$defs", "consentMode")
TRANSPORT_BEHAVIORS = schema_enum("common", "$defs", "consent", "properties", "transport_behavior")
WEB_CONSENT_MECHANISMS = schema_enum(
    "common", "$defs", "consent", "properties", "web_enforcement", "properties", "mechanism"
)
SERVER_CONSENT_MECHANISMS = schema_enum(
    "common", "$defs", "consent", "properties", "server_enforcement", "properties", "mechanism"
)
UNKNOWN_STATE_BEHAVIORS = schema_enum(
    "common", "$defs", "consent", "properties", "unknown_state_behavior"
)
CONSENT_SIGNAL_AUTHORITIES = schema_enum(
    "common", "$defs", "consent", "properties", "signal_authority"
)

DEDUP_STRATEGIES = schema_enum("run", "$defs", "dedup", "properties", "strategy")
DEDUP_SOURCE_TYPES = schema_enum("run", "$defs", "dedup", "properties", "source_type")

SHAPES = schema_enum("common", "$defs", "shapeNode", "properties", "shape")
FIELD_FLOW_STATUSES = schema_enum("common", "$defs", "fieldFlow", "properties", "status")
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


ROUTES = schema_enum("contract", "properties", "route")

REQUIREMENT_KINDS = schema_enum("common", "$defs", "requirementSemantics", "properties", "kind")

EVIDENCE_GRADES = schema_enum("common", "$defs", "authority", "properties", "grade")


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
