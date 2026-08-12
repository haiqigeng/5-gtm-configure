# Client-side GTM object surface

## Contents

- [Purpose](#purpose)
- [Classify the container and adapter](#classify-the-container-and-adapter)
- [Cover the complete applicable web surface](#cover-the-complete-applicable-web-surface)
- [Apply mutation authority by risk](#apply-mutation-authority-by-risk)
- [Handle workspace and shared-object integrity](#handle-workspace-and-shared-object-integrity)
- [Keep non-web resources outside scope](#keep-non-web-resources-outside-scope)
- [Verify the saved surface](#verify-the-saved-surface)

## Purpose

Treat expert client-side GTM configuration as more than tag creation. Discover every web-container
object type that can supply, control, group, restrict, or conflict with the requested setup. Load
this reference whenever the work involves a GTM element beyond an ordinary tag, trigger, or
user-defined variable, or when adapter coverage is uncertain.

Do not inventory the whole container. Inspect only the applicable object types and the individual
objects that can affect the requested requirements.

## Classify the container and adapter

Before designing objects:

1. prove the stable account, container, workspace, container type, and environment identity;
2. confirm that the target is a client-side web container;
3. discover the adapter's read, create, update, revert, and pagination capability per object type;
4. distinguish an absent object from an unsupported read operation;
5. block a required object family when authoritative saved-state readback is unavailable.

Never route a web requirement through server-container clients or Transformation resources merely
because an API exposes those endpoints.

A web Google tag that sets `server_container_url` remains a client-side object in scope: inspect
and preserve its browser transport field, measurement/destination identity, consumers, page-view
owner, and consent topology. The setting routes the browser request to the supplied endpoint; it
does not by itself create a second independent client request to the normal Google endpoint. The
receiving server container's clients, transformations, tags, routing, and deduplication remain
external to this skill.

## Cover the complete applicable web surface

Use this inventory as a routing checklist, not as permission to mutate every family:

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
| Environments | Inspect environment identity and destination isolation. Create or update an environment only with explicit environment authority; never publish to it. |
| Container settings | Change consent overview or another container-level setting only when it is directly required and explicitly authorized. |

Use the current official GTM UI/API and container state to determine which rows actually exist for
the target. Do not assume that MCP, API, export/import, and UI expose identical fields.

## Apply mutation authority by risk

Routine configuration authority covers required tags, triggers, variables, built-ins, folders, and
compatible installed-template use inside the dedicated workspace. The following high-impact
families require separate explicit authority:

- creating or changing a Zone, linked-container restriction, or security boundary;
- creating, reauthorizing, or changing an Environment;
- linking, moving, or detaching a Google destination;
- importing or upgrading a template that changes code or permissions for existing consumers;
- authoring or changing custom-template code;
- changing a container-level setting with effects outside the requested object graph;
- removing any object.

If the requested setup depends on one of these actions and authority is absent, keep independent
routine work judgeable and mark only the affected family `Blocked`.

## Handle workspace and shared-object integrity

Before updating a shared object, enumerate its relevant consumers and prove compatibility for
destination, source, consent route, environment, template version, automatic behavior, and future
change ownership. Synchronize workspace state and resolve conflicts only when the resolution is
fully in scope and preserves unrelated changes.

Do not use a container-wide object listing as a cleanup opportunity. A Zone, environment, template,
or destination discovered during configuration is integration evidence, not automatic mutation
scope.

## Keep non-web resources outside scope

Do not configure:

- server-container clients or server Transformation objects;
- server-side tags, Conversions API, event-ID, or browser/server deduplication;
- account users and permissions;
- website snippets or application code;
- container versions, approvals, Submit, or publication;
- another container merely because it is linked by a Zone or destination.

## Verify the saved surface

For every touched or reused object family, read back stable identity, full stored fields, references,
folder, consent, consumers, environment scope, template/version, and fingerprint when available.
Confirm that required built-ins are enabled, every reference resolves, high-impact families remain
untouched unless explicitly authorized, and an identical recomputation is a no-op.
