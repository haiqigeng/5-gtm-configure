# ruff: noqa: E402
import copy
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import TargetAdapterRegistry, execute_ready_operations, verify_idempotent_rerun
from adapter_support import AmbiguousWriteError
from compile_configuration_request import compile_request
from configuration_run import (
    atomic_write,
    build_verification_comparison,
    checkpoint_operation,
    create_from_contract,
    load_document,
)
from current_support import valid_web_contract
from mcp_queue_adapter import FAMILIES, McpTargetAdapter

OUT = Path(sys.argv[1])
clone = copy.deepcopy


def param(key, value, type="template"):
    return {"type": type, "key": key, "value": value}


def condition(left, right, type="equals"):
    return {"type": type, "parameter": [param("arg0", left), param("arg1", right)]}


def key(family, name):
    return f"web-main::{family}::{name}"


def request():
    c = valid_web_contract()
    c.pop("schema_version")
    c.pop("scope")
    c["requirements"] = [
        {
            "id": "REQ-LEAD",
            "authority": {
                "grade": "approved-input",
                "locator": "Synthetic user request: configure generate_lead after lead_success in dedicated workspace; reuse inspected CMP and trigger; preserve other edits",
            },
            "event_name": "generate_lead",
            "source_event": "lead_success",
            "parameters": {},
        }
    ]
    for e in c["evidence"]:
        if "supports" in e:
            e["supports"] = ["REQ-LEAD"]
    c["page_view_decisions"] = []
    top = c["execution_topologies"][0]
    top.update(
        tag_object_key=key("tag", "GA4 - generate_lead"),
        requirement_ids=["REQ-LEAD"],
        lifecycle_role="event-driven",
        normal_triggers=[
            {
                "trigger_object_key": key("trigger", "CE - lead_success"),
                "role": "source-event",
                "type": "custom-event",
            }
        ],
        blocking_trigger_keys=[key("trigger", "CMP - Analytics denied")],
        page_view_capable=False,
        page_view_destinations=[],
        page_view_occurrences=[],
    )
    consent = c["consent_topologies"][0]
    consent.update(
        requirement_ids=["REQ-LEAD"],
        event_coverage=["lead_success"],
        web_enforcement={"mechanism": "business-trigger-plus-vendor-block"},
    )
    c.pop("implementation")

    def obj(family, name, intended, action="reuse"):
        return {
            "resource_family": family,
            "name": name,
            "action": action,
            "intended": intended,
            "justification": "Implements synthetic approved lead request with inspected compatible dependencies",
            "evidence": ["approved-input", "official-current", "container-confirmed"],
            "risk": "routine",
        }

    c["objects"] = [
        obj(
            "tag",
            "GA4 - generate_lead",
            {
                "type": "gaawe",
                "parameter": [
                    param("eventName", "generate_lead"),
                    param("measurementIdOverride", "G-TEST123"),
                ],
                "firingTriggerId": [key("trigger", "CE - lead_success")],
                "blockingTriggerId": [key("trigger", "CMP - Analytics denied")],
                "tagFiringOption": "oncePerEvent",
            },
            "create",
        )
    ]
    c["reuse_candidates"] = [
        obj(
            "trigger",
            "CE - lead_success",
            {"type": "customEvent", "customEventFilter": [condition("{{_event}}", "lead_success")]},
        ),
        obj(
            "trigger",
            "CMP - Analytics denied",
            {
                "type": "customEvent",
                "customEventFilter": [condition("{{_event}}", ".*", "matchRegex")],
                "filter": [condition("{{CMP Analytics}}", "denied")],
            },
        ),
        obj(
            "variable",
            "CMP Analytics",
            {
                "type": "v",
                "parameter": [
                    param("name", "consent.analytics"),
                    param("dataLayerVersion", "2", "integer"),
                ],
            },
        ),
        obj("variable", "Unused candidate", {"type": "c", "parameter": [param("value", "unused")]}),
    ]
    return c


class FakeGtm:
    def __init__(self, req):
        self.data = {f: {} for f in FAMILIES}
        self.calls = []
        self.writes = []
        self.uncertain = False
        self.hide_once = False
        for n, o in enumerate(req["reuse_candidates"], 101):
            f = o["resource_family"]
            idf = FAMILIES[f][1]
            self.data[f][str(n)] = {
                **clone(o["intended"]),
                "name": o["name"],
                idf: str(n),
                "fingerprint": "1",
            }
        self.data["tag"]["999"] = {
            "tagId": "999",
            "name": "Unrelated pre-existing edit",
            "type": "html",
            "parameter": [param("html", "<div>existing edit</div>")],
            "notes": "keep this unsaved-to-version work",
            "fingerprint": "7",
        }

    def call(self, tool, args):
        self.calls.append([tool, clone(args)])
        t = tool.removeprefix("synthetic__")
        a = args["action"]
        if t == "gtm_workspace":
            return (
                {
                    "accountId": "account-1",
                    "containerId": "GTM-WEBTEST",
                    "workspaceId": "workspace-web",
                }
                if a == "get"
                else {
                    "workspaceChange": [
                        {"changeStatus": "updated", "tag": clone(self.data["tag"]["999"])}
                    ]
                }
            )
        if t == "gtm_container":
            return {"accountId": "account-1", "containerId": "GTM-WEBTEST", "usageContext": ["web"]}
        f = next(f for f, v in FAMILIES.items() if v[0] == t)
        idf = FAMILIES[f][1]
        if a == "list":
            items = list(self.data[f].values())
            start = (args["page"] - 1) * args["itemsPerPage"]
            return {f: clone(items[start : start + args["itemsPerPage"]])}
        if a == "get":
            if self.hide_once and f == "tag" and args[idf] != "999":
                self.hide_once = False
                raise RuntimeError("Synthetic connection failed after save")
            return clone(self.data[f][args[idf]])
        self.writes.append([f, a, clone(args)])
        if a in {"create", "update"}:
            ident = str(500 + len(self.writes)) if a == "create" else args[idf]
            value = {**clone(args["createOrUpdateConfig"]), idf: ident, "fingerprint": "2"}
            self.data[f][ident] = value
            if self.uncertain:
                self.uncertain = False
                self.hide_once = True
                raise AmbiguousWriteError("Synthetic connection interrupted after commit")
            return clone(value)
        raise AssertionError(a)


PROFILE = {
    "tool_prefix": "synthetic__",
    "workspace_path": [],
    "container_path": [],
    "status_path": [],
    "families": {
        f: {
            "actions": ["list", "get", "create", "update"],
            "first_page": 1,
            "page_size": 2,
            "list_path": [f],
            "object_path": [],
        }
        for f in ("tag", "trigger", "variable")
    },
}


def bind(c, backend):
    reg = TargetAdapterRegistry()
    ad = McpTargetAdapter(c["targets"][0], PROFILE, backend.call)
    reg.register(c["targets"][0], ad, ad.capabilities())
    return reg, ad


def init(c, name):
    path = OUT / (name + ".json")
    atomic_write(
        path,
        create_from_contract(c, run_id=name, source_locator="Independent synthetic evaluation"),
    )
    return path


def snapshot(backend, name):
    (OUT / (name + "-saved.json")).write_text(json.dumps(backend.data, indent=2))


def run():
    req = request()
    (OUT / "request.json").write_text(json.dumps(req, indent=2))
    c = compile_request(req)
    assert len(c["implementation"]["objects"]) == 4, "Only reachable dependencies should compile"
    (OUT / "compiled-contract.json").write_text(json.dumps(c, indent=2))
    backend = FakeGtm(req)
    unrelated = clone(backend.data["tag"]["999"])
    reg, ad = bind(c, backend)
    p = init(c, "create")
    execute_ready_operations(p, reg)
    verify_idempotent_rerun(p, reg)
    assert load_document(p)["run"]["status"] == "Configured"
    assert len(backend.writes) == 1
    saved = next(v for v in backend.data["tag"].values() if v["name"] == "GA4 - generate_lead")
    assert saved["firingTriggerId"] == ["101"] and saved["blockingTriggerId"] == ["102"]
    assert backend.data["tag"]["999"] == unrelated
    assert {x["key"]: x["value"] for x in saved["parameter"]} == {
        "eventName": "generate_lead",
        "measurementIdOverride": "G-TEST123",
    }
    snapshot(backend, "create")
    print(
        "PASS create, compiler reuse closure, native reference translation, saved-state and unrelated edit preservation"
    )
    # Approved narrow correction to a tag retaining an existing note.
    saved["notes"] = "existing owner annotation"
    update = request()
    row = update["objects"][0]
    row.update(action="update", object_id=saved["tagId"], pre_change=clone(saved))
    row["intended"] = clone(saved)
    row["intended"].pop("tagId")
    row["intended"].pop("fingerprint")
    row["intended"]["parameter"][1]["value"] = "G-UPDATED"
    row["intended"]["firingTriggerId"] = [key("trigger", "CE - lead_success")]
    row["intended"]["blockingTriggerId"] = [key("trigger", "CMP - Analytics denied")]
    c2 = compile_request(update)
    p2 = init(c2, "update-mcp")
    reg2, ad2 = bind(c2, backend)
    execute_ready_operations(p2, reg2)
    failed = next(o for o in load_document(p2)["object_changes"] if o["resource_family"] == "tag")
    if failed["state"] != "verified":
        print("DEFECT packaged MCP update:", failed["journal"][-1])
        from verification import build_pre_write_comparison

        (OUT / "update-false-drift-comparison.json").write_text(
            json.dumps(build_pre_write_comparison(failed, ad2.read(failed))[0], indent=2)
        )
        raise AssertionError("Packaged MCP update must succeed without adapter workarounds")
    verify_idempotent_rerun(p2, reg2)
    after = backend.data["tag"][saved["tagId"]]
    assert after["notes"] == "existing owner annotation"
    assert backend.data["tag"]["999"] == unrelated
    assert len(backend.writes) == 2
    assert after["parameter"][1]["value"] == "G-UPDATED"
    snapshot(backend, "update")
    print("PASS update preserves same-tag annotation and unrelated pre-existing workspace edit")
    # New independent backend, committed write but failed immediate read; resume using documented read/checkpoint.
    b3 = FakeGtm(req)
    b3.uncertain = True
    reg3, ad3 = bind(c, b3)
    p3 = init(c, "uncertain")
    execute_ready_operations(p3, reg3)
    d = load_document(p3)
    op = next(o for o in d["object_changes"] if o["resource_family"] == "tag")
    assert op["state"] == "uncertain"
    assert len(b3.writes) == 1
    execute_ready_operations(p3, reg3)
    assert len(b3.writes) == 1, "No blind uncertain retry"
    fresh_reg, fresh_ad = bind(c, b3)
    # A fresh MCP adapter needs authoritative dependency inventory for ID context.
    for f in ("trigger", "variable"):
        cursor = None
        while True:
            page = fresh_ad.list_resource_page(f, cursor)
            cursor = page["next_cursor"]
            if cursor is None:
                break
    observed = fresh_ad.read(op)
    cmp, safe = build_verification_comparison(op, observed)
    d = checkpoint_operation(
        d,
        operation_id=op["operation_id"],
        state="verified",
        note="Independent synthetic recovery authoritative readback",
        comparison=cmp,
        saved=safe,
    )
    atomic_write(p3, d)
    verify_idempotent_rerun(p3, fresh_reg)
    assert len(b3.writes) == 1
    assert load_document(p3)["run"]["status"] == "Configured"
    snapshot(b3, "uncertain")
    print("PASS uncertain save recovered by readback with no second mutation")

    from configuration_run import build_pre_write_comparison

    doc = load_document(OUT / "update-mcp.json")
    op = next(o for o in doc["object_changes"] if o["resource_family"] == "tag")
    raw = clone(op["pre_change"])
    primary = {**raw, "target_id": op["target_id"], "object_type": op["resource_family"]}
    graph = {"objects": [primary], "context_objects": []}
    assert build_pre_write_comparison(op, graph)[0]["pass"]
    assert build_pre_write_comparison(op, raw)[0]["pass"]
    for label, bad in [
        ("wrong-target", {"objects": [{**primary, "target_id": "different-workspace"}]}),
        ("wrong-family", {"objects": [{**primary, "object_type": "trigger"}]}),
        ("multiple-primary", {"objects": [primary, primary]}),
        ("no-primary", {"objects": []}),
        ("invalid-shape", {"objects": {"unexpected": primary}}),
    ]:
        try:
            build_pre_write_comparison(op, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(label + " accepted")
    for label, changed in [
        ("rename", {"name": "Another tag"}),
        ("foreign-id", {"tagId": "000"}),
        ("unrelated-new-field", {"notes": "concurrent analyst edit"}),
        ("new-parameter", {"parameter": raw["parameter"] + [param("unreviewed", "true")]}),
    ]:
        comparison, _ = build_pre_write_comparison(op, {"objects": [{**primary, **changed}]})
        assert not comparison["pass"], label + " accepted"
    print(
        "PASS graph identity guards (target/family/cardinality/shape), raw read support, name/ID/field/parameter drift rejection"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
