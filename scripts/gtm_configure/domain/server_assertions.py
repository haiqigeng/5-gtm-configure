"""Server semantics reviewed against an exact native snapshot, never invented API fields."""

from gtm_configure.core.validation import canonical_sha256


def validate_server_assertions(item, path, fail):
    family, action = item["resource_family"], item["action"]
    native = item.get("intended") or {}
    assertions = item.get("assertions", {})
    obsolete = {
        "claim_criteria",
        "scope",
        "mode",
        "variable_type",
        "key_path",
        "claiming_client_proof",
        "secret_fields",
        "allowed_parameters",
    } & set(native)
    if obsolete:
        fail(
            f"{path}.intended contains review metadata instead of native GTM fields: {sorted(obsolete)}"
        )
    if action == "remove":
        return
    required = (
        "client_claim"
        if family == "client"
        else "transformation"
        if family == "transformation"
        else "event_data"
        if family == "variable" and native.get("type") == "ed"
        else None
    )
    if required and required not in assertions:
        fail(f"{path}.assertions.{required} must describe the reviewed native behavior")
    for kind, assertion in assertions.items():
        expected_family = {
            "client_claim": "client",
            "transformation": "transformation",
            "event_data": "variable",
        }[kind]
        if family != expected_family:
            fail(f"{path}.assertions.{kind} does not apply to {family}")
        if assertion["native_sha256"] != canonical_sha256(native):
            fail(f"{path}.assertions.{kind} is stale: review the exact intended native snapshot")
    if family == "client":
        if type(native.get("priority")) is not int:
            fail(f"{path}.intended.priority must explicitly record the reviewed integer priority")
        if action in {"create", "update", "replace"} and item.get("risk") != "high-impact":
            fail(f"{path}.risk must be high-impact for Client claim behavior")
    if family == "transformation":
        scope = assertions["transformation"]["scope"]
        if scope != "single-destination" and item.get("risk") != "high-impact":
            fail(f"{path}.risk must be high-impact for a shared Transformation")
