---
name: configure-gtm
description: "Configure approved analytics, media, consent, and scoped organization changes in authorized GTM web/server workspaces or connected pipelines. Save and verify objects through MCP, API, import, or UI. Excludes tracking-plan design, general audit/cleanup, runtime QA, publication, and version creation."
---

# Configure Google Tag Manager

Deliver the approved change as a saved, readback-verified object graph in authorized web/server
workspaces. Preserve approved semantics and pre-existing edits. The [authority contract](references/core/authority.md)
owns scope, approvals and the saved-configuration boundary.

Follow [the workflow](references/core/workflow.md), using [compact input](references/core/authoring.md#compact-input)
for mechanical preparation. Select [an adapter and its applicable guide](references/adapters/overview.md).
[Execution](references/core/execution.md) owns writes and recovery;
[acceptance](references/core/acceptance.md) owns the verdict and handoff.

## Load guidance for the changed feature

| Change | Read |
| --- | --- |
| Scope or authorization uncertainty | [Authority](references/core/authority.md) |
| Product/template semantics or capability | [Evidence policy](references/core/evidence.md) |
| Folder organization or native reuse | [Organization](references/organization.md) |
| Approved GA4 delivery or exact analytics conformance | [Intake and conformance](references/analytics/intake-and-conformance.md) |
| GA4 tags | [GA4](references/analytics/ga4.md) |
| Other analytics | [Web vendors](references/analytics/web-vendors.md) or [server vendors](references/analytics/server-vendors.md) |
| Media | [Media route](references/media/common.md) or [server media](references/media/server.md), then only its vendor guide |
| Consent or CMP behavior | [Web consent](references/consent/web.md) or [server consent](references/consent/server.md) |
| First-party data | [Identity](references/data/identity.md), and [server identity](references/data/server-identity.md) when applicable |
| Source paths, types, shapes, missing values | [Mapping](references/data/mapping.md) |
| Web triggers, variables, sequencing | [Web execution](references/web/execution.md) |
| Additional object families | [Web resources](references/web/resources.md) or [server ingress](references/server/ingress.md) |
| Server Client or Event Data change | [Ingress](references/server/ingress.md), [server execution](references/server/execution.md), [native assertions](references/server/native-assertions.md) |
| Server Transformation | [Transformations](references/server/transformations.md) |
| Connected sender and receiver | [Pipeline architecture](references/pipeline/architecture-and-workflow.md) and [transport](references/pipeline/transport-data-contract.md) |
| Overlapping browser/server delivery | [Deduplication](references/pipeline/browser-server-deduplication.md) |
| Multiple destinations, brands, hosts or environments | [Routing](references/routing.md) |
| Template installation or permissions | [Templates](references/templates.md) |
| Full authorized tracking refonte | [Refonte](references/refonte.md) |

Load feature links when their decisions affect this change. Organization-only work uses native
capability and container evidence; collection, consent and pipeline work loads its corresponding
owners. Each guide supplies its feature-specific decisions within the shared authority contract.

## Tools and evidence

Resolve `<skill-dir>` to this skill's absolute path. Use
`python "<skill-dir>/scripts/configure_gtm.py" --help` for the command router.
Install `scripts/requirements.txt` once in the selected Python environment; the SDK host route
uses `scripts/requirements-mcp.txt`. For a GA4 delivery, start with `import-plan`.
Use `prepare` for compact input and `run` for the durable lifecycle. Schemas validate structure;
shared domain validators check semantics; the authenticated runtime journals and verifies writes.
Apply [evidence limits](references/core/authority.md#evidence-and-validation-limits) and
[privacy and comparison](references/core/execution.md#handle-secrets-without-false-equality)
throughout the lifecycle. The final verdict follows fresh read-only convergence.

For skill maintenance only, use [the release checks](references/maintenance.md).
