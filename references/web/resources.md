# Client-side GTM object surface

## Identify applicable resources

Discover the web resource families that supply, control, group, restrict or conflict with the approved
requirements. Verify account/container/workspace/type/environment and adapter capabilities through
[discovery](../adapters/discovery.md). Absent resources and unsupported reads are distinct states.
[Execution](../core/execution.md) owns complete baseline capture for applicable families and safe
freshness/recovery. Discovery establishes integration evidence; authority establishes mutations.

## Cover the applicable web surface

| Surface | Configuration responsibility |
| --- | --- |
| Workspace | Create/reuse the dedicated workspace, synchronize when safe, inspect conflicts, and attribute pre-existing versus current-run changes. |
| Tags | Configure native, installed-template, or narrowly justified custom tags, including consent and advanced settings. |
| Triggers | Configure normal triggers, exceptions, trigger groups, sequencing dependencies, and exact Boolean semantics. |
| User-defined variables | Configure DLVs, constants, settings variables, LUTs/RLTs, URL/cookie/DOM/auto-event variables, and narrow transformations. |
| Built-in variables | Enable only built-ins required by an approved trigger or mapping; record the consumer. |
| Folders | Create/reuse a shallow folder only when several related objects benefit. |
| Templates | Inspect/import/update an exact template only under template governance; verify permissions, version, fields, defaults, and consumers. |
| Google tag configuration | Discover Google tag configuration/settings objects and their connected consumers before changing fields. |
| Google destinations | Read linked destinations and reconcile shared execution and consent. Treat destination linking or movement as high impact and capability-gated. |
| Zones | Inspect restrictions when they can block the implementation. Configure a zone only with explicit zone authority. |
| Environments | Inspect environment identity and destination isolation. Use explicit environment authority under [target authority](../core/authority.md#target-authority). |
| Container settings | Change consent overview or another container-level setting only when it is directly required and explicitly authorized. |

Use current native UI/API/container evidence for actual fields and availability. Readback capability
is required for each affected family. [Authority](../core/authority.md#target-authority) owns high-impact
actions and workspace scope; [organization](../organization.md) owns shared-object compatibility;
[templates](../templates.md) owns template lifecycle.

## Keep target ownership explicit

[Google fields](../analytics/google-fields.md#treat-browser-transport-as-client-side-configuration)
owns web endpoint placement. Authorized [sender ID preparation](../pipeline/browser-server-deduplication.md)
remains a web action. Receiver Clients/Transformations/tags belong to an authorized server target
or an external dependency. Use [server ingress](../server/ingress.md) for that surface and target-scoped
semantic identity for equally named objects.

## Verify the saved surface

Read back stable identity, full fields, references, folders, consent, consumers, environment,
template/version and available fingerprints. Confirm required built-ins, supported references,
authorized scope and no-op convergence through [execution](../core/execution.md).
