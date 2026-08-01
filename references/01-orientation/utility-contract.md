# Utility contract

## Contents

- [Audience](#audience)
- [North star](#north-star)
- [Operational quality](#operational-quality)
- [Requirement authority](#requirement-authority)
- [Intake](#intake)
- [Operational output](#operational-output)
- [Workspace authority](#workspace-authority)
- [Boundaries](#boundaries)

## Audience

Serve an expert web analyst configuring client-side Google Tag Manager. The analyst owns approved
analytics semantics, media objectives and identities, and client consent policy. The agent owns
current technical research, the in-scope GTM architecture, mutation, saved-state proof, and handoff.

## North star

Operationally implement an approved analytics tracking plan and, when requested, an explicit media
implementation brief inside a client-side GTM workspace as a clean, well-organized, technically
correct, best-practice, consent-controlled saved setup.

Cover every applicable client-side object family, preserve approved analytics semantics, configure
media from its own current official browser schema, apply strict/basic CMP control by default, and
verify the saved graph. The operational result is the saved GTM object graph. Analysis, a plan, or a
complete specification is not successful configuration. Never publish.

## Operational quality

| Quality | Operational meaning |
| --- | --- |
| Clean | No avoidable in-scope duplicate, unresolved conflict, redundant helper, or speculative object. This does not authorize general cleanup. |
| Well organized | Clear naming, shallow folders when useful, readable ownership, and semantic reuse. |
| Correct | Faithful authority, current technical validity, compatible source/template fields, correct triggers and consent, and authoritative readback; not runtime certification. |
| Best practice | The smallest maintainable architecture satisfying the approved requirement and current documentation; never tracking-plan optimization. |
| Consent controlled | Strict/basic CMP blocking by default; advanced/native only when explicitly requested and proved for the exact browser product. |

## Requirement authority

Keep analytics and media business inputs separate.

| Route | Business authority | Technical authority |
| --- | --- | --- |
| Analytics | Approved tracking plan or exact direct analytics requirement | Current official destination, GTM, and installed-template documentation validates feasibility but never rewrites valid approved semantics. |
| Media | Explicit human media-team brief: product, business action, use, and destination identity | Current official vendor browser documentation and the inspected installed template establish the destination schema. |
| Consent | Default strict/basic route or another explicit client-approved product policy | Current official CMP, vendor, GTM, and template behavior. |

Use the tracking plan only as supporting evidence for a media source event or value. A media event
need not appear in the analytics plan; never copy a GA4 destination name or payload to another
vendor by analogy. Container state proves integration, consumers, conflicts, and possible reuse,
not best practice.

## Intake

Discover before asking. Resolve the target account, web container, dedicated workspace, adapter
capabilities, environment, relevant objects/consumers, installed template, CMP, and safe official
facts. Then batch only the unresolved facts that block a configuration decision:

- analytics: approved scope, event/fields/literals, source mappings, filters, and business timing;
- media: product, action, intended use, destination identity, and conditional labels or catalog IDs;
- source: dataLayer event/path, type/shape/timing, and a representative payload only when a real
  transformation or ambiguous array requires it;
- consent/first-party data: exact approved route, sources, product support, and external activation.

Do not ask whether the analyst wants read-only, planning, or mutation for an actual configuration
request. Do not require a separate source-contract document when approved inputs and container
evidence establish the facts. A missing design-time source or supported field blocks; a mapped
runtime value that may be empty is a site/dataLayer and recette dependency, not authority for a
payload-eligibility helper.

## Operational output

Return the dedicated workspace and one evidence-backed result per requirement: `Configured`,
`Partial`, `Blocked`, or `Deferred`. Include the requirement-to-object graph, payload and consent
maps, saved IDs/readback, official sources, exact recovery boundary, idempotency result, external
owners, and confirmation that the run did not execute GTM Preview, publish, Submit, or create a GTM
version. Produce the versioned machine handoff when the execution surface permits it.

Unavailable write access is `Blocked`, not a successful specification. A failure after a current-
run save is `Partial`; preserve the exact saved state and next safe readback action.

## Workspace authority

A request to configure a named container authorizes read and routine in-scope create/update/reuse
inside a dedicated workspace. Resolve it by stable ID, record synchronization/conflicts and pre-
existing changes, and avoid Default Workspace unless explicitly accepted.

It does not authorize publication, general cleanup, unrelated refactoring, deletion/replacement,
another container, template permission expansion, destination movement, Zone/environment/container-
setting changes, or external-system mutation. Those actions require their existing explicit
authority. Preserve unrelated work.

## Boundaries

This skill does not design a tracking plan, develop a site/dataLayer, perform a general audit or
cleanup, execute GTM Preview/browser/network/CMP/vendor recette, decide law or policy, administer
GA4/media/CMP accounts, publish, or create versions.

Server-side GTM, Conversions API, and browser/server deduplication remain future extensions. Map an
explicitly approved browser `event_id` only when current browser documentation and the installed
template support it; never generate the ID or design its server owner.
