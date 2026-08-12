---
name: configure-gtm
description: "Operationally configure complete client-side Google Tag Manager web containers for expert web analysts. Convert approved analytics plans, exact analytics requirements, and explicit media briefs into clean, technically correct, consent-controlled saved GTM object graphs across applicable tags, triggers, variables, folders, templates, Google tag configuration/destinations, workspaces, Zones, environments, and settings. Use current official documentation and installed-template capabilities, preserve approved analytics semantics, apply basic CMP blocking by default, and use advanced consent only when explicitly requested. Use for actual GTM mutation through an MCP, API, export/import path, or signed-in UI. Do not use for tracking-plan design, general audit/cleanup, site/dataLayer work, legal decisions, runtime recette/certification, publication, or server-side GTM; server-side GTM and browser/server deduplication are future extensions."
---

# Configure Google Tag Manager

Operationally implement an approved analytics tracking plan and, when requested, an explicit media
implementation brief in a client-side GTM workspace. Create, update, or reuse every required GTM
object, verify saved state, and never publish. Treat the saved, verified GTM object graph as the unit
of success; a plan or specification is not configuration.

When the input is a `ga4-tracking-plan` delivery directory, run
`python scripts/import_ga4_tracking_plan_handoff.py DELIVERY -o approved-semantics.json` first.
The importer verifies approval and every artifact hash, preserves stable event and opportunity
identity, rejects malformed machine records, and supplies approved semantics to the configuration
map without reinterpreting the workbook.

## 01 - Orientation

Read [utility-contract.md](references/01-orientation/utility-contract.md) at the start. Read
[official-source-policy.md](references/01-orientation/official-source-policy.md) when beginning the
required live product/template/CMP research. Load detailed references only when their route applies.

## 02 - Execution

Read [implementation-workflow.md](references/02-execution/implementation-workflow.md) for every run.
Before mutation, use [configuration-contract.md](references/02-execution/configuration-contract.md).
For durable checkpoints and machine handoff, use
[configuration-run-and-resume.md](references/02-execution/configuration-run-and-resume.md) and its
[configuration-run schema](schemas/configuration-run.schema.json).

| Requirement | Read |
| --- | --- |
| Object-family coverage, built-ins, Google tag configuration/destinations, Zones, environments, settings | [client-side-object-surface.md](references/02-execution/client-side-object-surface.md) |
| Tracking plan, direct analytics requirement, workbook scope, conformance | [tracking-plan-fidelity-and-conformance.md](references/02-execution/tracking-plan-fidelity-and-conformance.md) |
| Existing-container tracking refonte plus client tag inventory | [tracking-refonte.md](references/02-execution/tracking-refonte.md) |
| Google tag or GA4 | [analytics-tags.md](references/02-execution/analytics-tags.md) |
| Google tag field placement, settings variables, page-view/ecommerce ownership, browser transport | [google-field-ownership.md](references/02-execution/google-field-ownership.md) |
| GA4 validity, limits, reserved names, PII, property-health effects | [ga4-collection-safety.md](references/02-execution/ga4-collection-safety.md) |
| Non-GA4 browser analytics | [analytics-vendors.md](references/02-execution/analytics-vendors.md) |
| Multiple destinations, brands, regions, hosts, environments | [multi-destination-routing.md](references/02-execution/multi-destination-routing.md) |
| Any browser media implementation | [media-tags.md](references/02-execution/media-tags.md) |
| Google Ads | [media-google-ads.md](references/02-execution/media-google-ads.md) |
| Floodlight / Campaign Manager 360 | [media-floodlight.md](references/02-execution/media-floodlight.md) |
| Microsoft Advertising / Bing Ads | [media-microsoft-ads.md](references/02-execution/media-microsoft-ads.md) |
| Meta Pixel | [media-meta.md](references/02-execution/media-meta.md) |
| TikTok Pixel | [media-tiktok.md](references/02-execution/media-tiktok.md) |
| Snap Pixel | [media-snapchat.md](references/02-execution/media-snapchat.md) |
| LinkedIn Insight Tag | [media-linkedin.md](references/02-execution/media-linkedin.md) |
| Pinterest Tag | [media-pinterest.md](references/02-execution/media-pinterest.md) |
| X Pixel | [media-x.md](references/02-execution/media-x.md) |
| Reddit Pixel | [media-reddit.md](references/02-execution/media-reddit.md) |
| Criteo OneTag | [media-criteo.md](references/02-execution/media-criteo.md) |
| Affiliate/partner browser tag | [media-affiliate.md](references/02-execution/media-affiliate.md) |
| CMP blocking or lifecycle | [cmp-consent.md](references/02-execution/cmp-consent.md) |
| OneTrust, Didomi, Axeptio, or discovered CMP | [cmp-platform-patterns.md](references/02-execution/cmp-platform-patterns.md) |
| IAB TCF / Additional Consent | [tcf-consent.md](references/02-execution/tcf-consent.md) |
| Advanced/native/cookieless/anonymous consent | [vendor-consent-modes.md](references/02-execution/vendor-consent-modes.md) |
| Google Consent Mode | [google-consent-mode.md](references/02-execution/google-consent-mode.md) |
| First-party user data, enhanced conversions, advanced matching | [first-party-data.md](references/02-execution/first-party-data.md) |
| dataLayer, ecommerce arrays, missing values, transformations | [data-contract-and-transformations.md](references/02-execution/data-contract-and-transformations.md) |
| Repeated projections/validation/transformation vectors | [transformation-patterns.md](references/02-execution/transformation-patterns.md) |
| Conversion Linker or cross-domain measurement | [conversion-linker-cross-domain.md](references/02-execution/conversion-linker-cross-domain.md) |
| Triggers, variables, SPA, firing settings, sequencing | [triggers-and-variables.md](references/02-execution/triggers-and-variables.md) |
| Native, official, community, or custom templates | [template-governance.md](references/02-execution/template-governance.md) |
| MCP, API, export/import, UI | [tool-adapters.md](references/02-execution/tool-adapters.md) |
| Naming, folders, constants, LUT/RLT, reuse | [naming-and-reuse.md](references/02-execution/naming-and-reuse.md) |

## 03 - Judgement

Before assigning status, read
[acceptance-and-handoff.md](references/03-judgement/acceptance-and-handoff.md). Use `Configured` only
after authoritative readback; otherwise use the narrowest accurate `Partial`, `Blocked`, or
`Deferred` result.

## Operational rules

- Treat a named-container configuration request as authority to discover and perform routine
  in-scope create/update/reuse in a dedicated workspace. It does not authorize cleanup, unrelated
  changes, removal/replacement, high-impact governance, another system, publication, or versions.
- Discover target, workspace, source, relevant consumers/conflicts, adapter capabilities,
  installed template, CMP, and current official facts before batching genuine blockers.
- Implement approved analytics event names, fields, sources, literals, filters, and timing exactly.
  Report valid advisories; stop invalid/reserved/missing-required/incompatible requirements.
- Treat the media brief as business authority and the vendor's current browser documentation as
  schema authority. Never translate from GA4 or another vendor by analogy.
- Use a compatible native or supported template whenever one exists. Inspect its version, fields,
  permissions, defaults, and automatic behavior. Unsupported mutation is `Blocked`, not silent
  Custom HTML.
- Select best-practice architecture before reuse. Inspect only the objects related to the requested
  implementation; container state is evidence for integration and reuse, never as proof of best
  practice or authority for general audit.
- Classify the request as greenfield or a delta. Trace shared consumers, capture fingerprints and
  pre-change state, and use one governed `replace` action only when authorized update is impossible.
- Default every product to strict/basic CMP blocking. Attach the complete reusable vendor block set
  to every in-scope vendor base/configuration and event tag. Select a verified CMP readiness/grant
  event independently when it supplies the initial or later-grant firing opportunity; it does not
  replace the block. Use that CMP event plus the block for baseline/page-load tags and the approved
  business Custom Event plus the block for business tags. Do not duplicate the block with
  Additional Consent Checks. Record template-owned built-in checks separately. Advanced/native
  behavior requires an explicit request and exact current proof and must not receive a defeating
  block or Additional Consent Check.
- Build the smallest understandable object graph. Follow the default naming convention, use a
  shallow folder when helpful, prefer direct DLV/template mappings, use settings variables only for
  real sharing, LUT/RLT for deterministic routing, and narrow Custom JavaScript only for required
  shape conversion.
- Resolve every outgoing field before writing: approved actual source and source shape, destination
  shape, GTM method, template field, and missing behavior. Never infer a dataLayer source from a
  destination field name; use a direct mapping only when the complete shapes are compatible.
- Preserve every required ecommerce item and destination shape. Never invent IDs/fields, drop
  items, or create payload-eligibility variables or validity triggers merely because runtime data
  can be absent.
- Assign exactly one page-view owner per destination, reconcile pre-CMP business events, and bind
  every active tag's typed semantic normal-trigger references and vendor blocks to its exact target
  `firingTriggerId`/`blockingTriggerId` arrays before writing. Record Additional/built-in checks,
  firing option, destinations, environments, and shared execution units. A removed or paused tag
  has pre-change evidence and an inventory disposition, not a fictional target firing topology.
- For a tracking refonte, capture one complete paginated baseline, disposition every in-scope
  inventory tag, rebuild analytics from the new plan, recursively remap retained consumers, and
  preserve inventory row order in the user-facing change log. Do not turn refonte authority into
  unrelated cleanup or implicit destructive authority.
- Maintain the versioned run artifact when possible. Never overwrite saved run history; serialize
  writers for the same artifact; before a delta write, prove fresh saved state still matches
  `pre_change`; never overwrite a conflicting create; checkpoint around each write; re-read every
  saved/reused object; bind structured comparison evidence to authoritative readback; never retry
  ambiguity; make an identical rerun a no-op, then use the single locked finalization transition.
- Record site, CMP, GA4/media administration, catalog/feed, recette, publication, and server work as
  external. Never claim GTM completed another system or runtime validation.
- Keep server-side GTM, CAPI, and deduplication as future extensions. Never generate a browser event
  ID; map an explicitly approved browser value only when current documentation/template supports it.
