"""Shared enums and immutable policy constants for configuration-run@2.1."""

SCHEMA_VERSION = "2.1"
LEGACY_SCHEMA_VERSIONS = {"2.0"}
VERIFICATION_SCHEMA_VERSION = "1.0"
RUN_PHASES = {"preflight", "mutation", "readback", "complete"}
RUN_STATUSES = {"In progress", "Configured", "Partial", "Blocked", "Deferred"}
REQUIREMENT_STATUSES = {"In progress", "Configured", "Partial", "Blocked", "Deferred"}
OPERATION_STATES = {
    "planned",
    "in_progress",
    "saved",
    "verified",
    "failed",
    "uncertain",
    "skipped",
}
CONSENT_MODES = {"strict-basic", "advanced-native"}
CONSENT_MECHANISMS = {"blocking-trigger", "grant-event", "native-advanced"}
MAPPING_STATUSES = {"pending", "mapped", "intentionally-omitted", "external", "blocked"}
MAPPING_METHODS = {
    "constant",
    "custom-javascript",
    "direct-dlv",
    "lookup-table",
    "native-template",
    "regex-table",
    "settings-variable",
}
SHAPE_COMPATIBILITY = {"compatible", "conversion-required"}
EXTENDED_MAPPING_KEYS = {
    "source_authority_grade",
    "source_authority_locator",
    "source_shape",
    "destination_shape",
    "shape_compatibility",
    "mapping_method",
    "missing_behavior",
}
DEFAULT_VENDOR_BLOCK_SCOPE = "regex:.*"
EXECUTION_MODES = {"isolated-lightweight", "isolated-durable", "refonte-durable"}
LIFECYCLE_ROLES = {"baseline-page-load", "event-driven"}
NORMAL_TRIGGER_ROLES = {
    "cmp-readiness-grant",
    "initialization-page-load",
    "source-event",
}
NORMAL_TRIGGER_TYPES = {
    "click-all-elements",
    "click-just-links",
    "consent-initialization",
    "custom-event",
    "dom-ready",
    "element-visibility",
    "form-submission",
    "history-change",
    "initialization",
    "javascript-error",
    "page-view",
    "scroll-depth",
    "timer",
    "trigger-group",
    "window-loaded",
    "youtube-video",
}
PAGE_LOAD_TRIGGER_TYPES = {
    "consent-initialization",
    "dom-ready",
    "initialization",
    "page-view",
    "window-loaded",
}
TRIGGER_TYPE_ALIASES = {
    "always": "page-view",
    "click": "click-all-elements",
    "clickallelements": "click-all-elements",
    "clickjustlinks": "click-just-links",
    "consentinit": "consent-initialization",
    "linkclick": "click-just-links",
    "consentinitialization": "consent-initialization",
    "customevent": "custom-event",
    "domready": "dom-ready",
    "elementvisibility": "element-visibility",
    "formsubmission": "form-submission",
    "historychange": "history-change",
    "init": "initialization",
    "initialization": "initialization",
    "scripterror": "javascript-error",
    "javascripterror": "javascript-error",
    "jserror": "javascript-error",
    "pageview": "page-view",
    "scrolldepth": "scroll-depth",
    "timer": "timer",
    "triggergroup": "trigger-group",
    "windowloaded": "window-loaded",
    "youtubevideo": "youtube-video",
}
BUILT_IN_TRIGGER_TYPES = {
    "trigger::builtin::2147479553": "page-view",
    "trigger::builtin::2147479572": "consent-initialization",
    "trigger::builtin::2147479573": "initialization",
}
NON_EXECUTING_TAG_ACTIONS = {"pause", "remove"}
GOOGLE_CONFIGURATION_TAG_TYPES = {"gaawc", "googtag"}
GA4_EVENT_TAG_TYPES = {"gaawe"}
GOOGLE_ADS_CONVERSION_TAG_TYPES = {"awct"}
CUSTOM_CODE_TAG_TYPES = {"html", "img"}
FIRST_PARTY_PRODUCTS = {
    "ga4-user-id": "ga4",
    "ga4-user-provided-data": "ga4",
    "google-ads-enhanced-conversions": "google-ads",
    "google-ads-tag-wide-user-data": "google-ads",
    "google-ads-user-provided-data-event": "google-ads",
}
TAG_TYPE_ALIASES = {
    "ga4configuration": "gaawc",
    "ga4event": "gaawe",
    "googleanalyticsga4configuration": "gaawc",
    "googleanalyticsga4event": "gaawe",
    "googletag": "googtag",
}
CONFIGURATION_FIELD_ALIASES = {
    "userdata": {"userdata", "userdatavariable", "userprovideddata", "userprovideddatavariable"},
}
FIRING_OPTIONS = {"once-per-event", "once-per-page", "unlimited"}
PRE_CMP_POLICIES = {
    "not-applicable",
    "source-after-readiness",
    "later-fresh-event",
    "explicit-one-time-replay",
    "external-dependency",
}
PAGE_VIEW_OWNERS = {
    "google-tag-automatic",
    "dedicated-ga4-event",
    "external",
    "intentionally-none",
}
ECOMMERCE_ROUTES = {
    "not-applicable",
    "native-data-layer",
    "native-custom-object",
    "manual",
}
FIRST_PARTY_FEATURES = {
    "ga4-user-id",
    "ga4-user-provided-data",
    "google-ads-enhanced-conversions",
    "google-ads-tag-wide-user-data",
    "google-ads-user-provided-data-event",
    "vendor-advanced-matching",
}
INVENTORY_DISPOSITIONS = {
    "added",
    "keep",
    "update",
    "remap",
    "pause",
    "remove",
    "replace",
    "supersede",
}
TOP_LEVEL_KEYS = {
    "schema_version",
    "run",
    "requirements",
    "object_changes",
    "payload_mappings",
    "consent_routes",
    "container_baseline",
    "execution_topologies",
    "page_view_decisions",
    "first_party_data_routes",
    "inventory_dispositions",
    "saved_readback",
    "official_sources",
    "external_dependencies",
    "recovery_boundary",
    "idempotency",
    "recette_handoff",
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
