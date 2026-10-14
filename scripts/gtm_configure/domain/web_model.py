"""Shared current web-domain enums for configuration run."""

from gtm_configure.core.schemas import schema_enum

MAPPING_STATUSES = schema_enum("common", "$defs", "fieldBinding", "properties", "status")
MAPPING_METHODS = schema_enum(
    "common", "$defs", "fieldBinding", "properties", "mapping_method", "anyOf", 0
)
SHAPE_COMPATIBILITY = schema_enum(
    "common", "$defs", "fieldBinding", "properties", "shape_compatibility", "anyOf", 0
)
EXTENDED_MAPPING_KEYS = {
    "source_authority_grade",
    "source_authority_locator",
    "source_shape",
    "destination_shape",
    "shape_compatibility",
    "mapping_method",
    "missing_behavior",
}
LIFECYCLE_ROLES = schema_enum("common", "$defs", "tagPolicy", "properties", "lifecycle_role")
NORMAL_TRIGGER_ROLES = schema_enum("common", "$defs", "triggerRole", "properties", "role")
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
    "google-ads-server-user-data-transport": "google-ads-transport",
    "google-ads-server-user-provided-data-event": "google-ads-transport",
}
TAG_TYPE_ALIASES = {
    "ga4configuration": "gaawc",
    "ga4event": "gaawe",
    "googleanalyticsga4configuration": "gaawc",
    "googleanalyticsga4event": "gaawe",
    "googletag": "googtag",
}
CONFIGURATION_FIELD_ALIASES = {
    "userdata": {
        "userdata",
        "userdatavariable",
        "userprovideddata",
        "userprovideddatavariable",
    },
}
PRE_CMP_POLICIES = schema_enum("common", "$defs", "tagPolicy", "properties", "pre_cmp_policy")
PAGE_VIEW_OWNERS = schema_enum("common", "$defs", "pageViewDecision", "properties", "owner")
PAGE_VIEW_OCCURRENCES = schema_enum(
    "common", "$defs", "pageViewDecision", "properties", "occurrence"
)
FIRST_PARTY_FEATURES = schema_enum("common", "$defs", "firstPartyRoute", "properties", "feature")
INVENTORY_DISPOSITIONS = schema_enum(
    "common", "$defs", "inventoryDisposition", "properties", "disposition"
)
