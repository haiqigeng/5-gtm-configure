# Utility contract

## Contents

- [Audience](#audience)
- [North star](#north-star)
- [Operational quality](#operational-quality)
- [Requirement authority](#requirement-authority)
- [Run routes](#run-routes)
- [Intake](#intake)
- [Operational output](#operational-output)
- [Target authority](#target-authority)
- [Boundaries](#boundaries)

## Audience

Serve an expert web analyst configuring authorized Google Tag Manager web containers, server
containers, or their connected tagging pipeline. The analyst owns approved analytics semantics,
media objectives and identities, and client consent policy. The agent owns current technical
research, the in-scope GTM architecture, mutation, saved-state proof, and configuration result.

## North star

Operationally implement an approved analytics tracking plan and, when requested, an explicit media
implementation brief across authorized GTM web and associated server workspaces as a clean,
well-organized, technically correct, best-practice, consent-controlled setup.

The unit of success is the saved, verified GTM object graph for every authorized target. For a
pipeline it also includes the statically verified relationships between the sender, claiming
Client, generated Event Data, server consumers, consent signals, and destination routes. A plan,
prose specification, one-sided pipeline, or unsafe live cutover is not successful configuration.
Never publish or create a GTM version.

## Operational quality

| Quality | Operational meaning |
| --- | --- |
| Clean | No avoidable in-scope duplicate, unresolved conflict, redundant helper, speculative object, or accidental dual-delivery route. This does not authorize general cleanup. |
| Well organized | Clear target-aware naming, shallow folders when useful, readable ownership, and semantic reuse. |
| Correct | Faithful authority, current technical validity, compatible source/wire/Client/template fields, correct triggers and consent, and authoritative readback; not runtime certification. |
| Best practice | The smallest maintainable architecture satisfying the approved requirement and current documentation; never tracking-plan optimization. |
| Consent controlled | Strict/basic CMP control by default on the web route; advanced/native or server enforcement only when explicitly requested or required by the approved topology and proved for the exact product. |

## Requirement authority

Keep analytics and media business inputs separate.

| Route | Business authority | Technical authority |
| --- | --- | --- |
| Analytics | Approved tracking plan or exact direct analytics requirement | Current official destination, GTM, Client, and installed-template documentation validates feasibility but never rewrites valid approved semantics. |
| Media | Explicit human media brief: product, business action, use, and destination identity | Current official vendor documentation and the inspected installed web/server template establish each destination schema. |
| Consent | Default strict/basic route or another explicit client-approved product policy | Current official CMP, vendor, GTM, Client, and template behavior. |

Use a tracking plan only as supporting evidence for a media source event or value. A media event
need not appear in the analytics plan; never copy a GA4 destination name or payload to another
vendor by analogy. Existing container prevalence proves integration, consumers, conflicts, and
possible reuse, never as proof of best practice.

## Run routes

- `web`: one or more authorized web workspaces. Preserve the complete v8 web behavior baseline.
- `server`: one or more authorized server workspaces. Server objects use Client/Event Data/server
  semantics, never DOM, dataLayer, browser lifecycle, Custom HTML, or Custom JavaScript semantics.
- `pipeline`: at least one authorized web sender and one authorized server receiver. Model it as a
  graph: several senders may feed one Client and one claimed event may fan out to several tags.

Classify the route before loading conditional files. A web-only run must not require server facts.
A discovered endpoint is evidence, not authority to access or mutate its server container.

## Intake

Discover before asking. Resolve every named account/container/workspace by stable ID, confirm its
container type, inspect adapter capabilities, capture one complete paginated baseline per target,
and inspect relevant consumers, installed templates, CMP signals, and official sources. Then batch
only unresolved facts that change the architecture or authorization:

- analytics: approved scope, event/fields/literals, source mappings, filters, and business timing;
- media: exact browser/server product, action, use, destination identity, and credentials owner;
- source and transport: source path/type/shape/timing, endpoint owner, claiming Client behavior,
  generated Event Data, and a sample only when a real non-scalar ambiguity requires it;
- consent and first-party data: approved route, signal coverage, sources, consumers, normalization/
  hashing owner, and external activation;
- dual delivery: destination overlap, stable occurrence identity, exact browser/server fields, and
  companion matching fields.

Do not ask whether an actual named-container configuration request should mutate. Do not require a
separate source-contract document when approved inputs and container evidence establish the facts.
A missing design-time source or supported field blocks; a mapped runtime value that may be empty is
a site/dataLayer and recette dependency, not authority for payload-eligibility variables.

## Operational output

Return the dedicated workspaces and one evidence-backed result per requirement and target:
`Configured`, `Partial`, `Blocked`, or `Deferred`. Include the requirement-to-object graph,
field/transport/consent/dedup maps, saved IDs and readback, official sources, recovery frontier,
idempotent rerun result, external owners, publication dependencies, and confirmation that no
Preview, publication, Submit, or version creation occurred.

Runtime recette remains independent: it uses the tracking plan and live GTM/Preview evidence, not a
configure-gtm artifact. Unavailable write access is `Blocked`, not a successful specification. A
failure after a save is `Partial` with the exact next readback.

## Target authority

A request to configure a named target authorizes read and routine in-scope create/update/reuse in
its dedicated workspace. Web authority does not grant server authority and server authority does
not grant web authority. Avoid Default Workspace unless explicitly accepted.

Explicit high-impact authority remains required for deletion/replacement, pausing, shared Client
claim or priority changes, broad Transformations, template import/upgrade/permission expansion,
Zones/environments/container settings, and a live sender endpoint cutover. Preserve unrelated and
pre-existing workspace work. Inspect only the objects related to the requested implementation
unless a separately authorized refonte or audit requires complete inventory reconciliation.

## Boundaries

This skill does not design a tracking plan, develop a site/dataLayer, provision a cloud tagging
server, configure DNS/CDN, call vendor APIs outside GTM, perform a general audit or cleanup, execute
Preview/browser/server/network/CMP/vendor recette, decide law or policy, administer analytics/media/
CMP accounts, generate credentials, publish, or create versions.

Measurement Protocol, mobile-app, CRM, offline, and arbitrary backend ingress remain future
extensions. The run model may represent future ingress without implying current implementation
support.
