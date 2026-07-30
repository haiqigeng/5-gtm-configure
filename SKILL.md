---
name: configure-gtm
description: "Operationally configure complete client-side Google Tag Manager web containers for expert web analysts. Convert approved analytics plans, exact analytics requirements, and explicit media briefs into clean, technically correct, consent-controlled saved GTM object graphs across applicable tags, triggers, variables, folders, templates, Google tag configuration/destinations, workspaces, Zones, environments, and settings. Use current official documentation and installed-template capabilities, preserve approved analytics semantics, apply basic CMP blocking by default, and use advanced consent only when explicitly requested. Use for actual GTM mutation through an MCP, API, export/import path, or signed-in UI. Do not use for tracking-plan design, general audit/cleanup, site/dataLayer work, legal decisions, runtime recette/certification, publication, or server-side GTM; server-side GTM and browser/server deduplication are future extensions."
---

# Configure Google Tag Manager

Operationally implement an approved analytics tracking plan and, when requested, an explicit media implementation brief
inside a client-side GTM workspace as a clean, well-organized, technically
correct, best-practice, and consent-controlled setup. Cover every applicable web-container object.
Create, update, or reuse every required GTM object, verify every saved change, and never publish.

Treat the saved, verified GTM object graph as the unit of success. A plan, recommendation, or
object-level specification is not a substitute for configuration. Keep the mandatory loop short and
load detailed playbooks only for the requirements present.

## 01 - Orientation

Read for every configuration:

- [utility-contract.md](references/01-orientation/utility-contract.md)
- [official-source-policy.md](references/01-orientation/official-source-policy.md)

## 02 - Execution

Read for every configuration:

- [implementation-workflow.md](references/02-execution/implementation-workflow.md)
- [configuration-contract.md](references/02-execution/configuration-contract.md), used as a concise
  internal requirement-to-object map for mutation and saved-state readback.

Load only the applicable detailed playbooks:

| Configuration requirement | Read |
| --- | --- |
| Any configuration involving object-family coverage, built-in variables, Google tag configuration, destinations, Zones, environments, or container settings | [client-side-object-surface.md](references/02-execution/client-side-object-surface.md) |
| Approved analytics tracking plan, exact direct analytics requirement, workbook scope, or exact conformance | [tracking-plan-fidelity-and-conformance.md](references/02-execution/tracking-plan-fidelity-and-conformance.md) |
| Google tag or GA4 analytics | [analytics-tags.md](references/02-execution/analytics-tags.md) |
| GA4 validity, limits, reserved names, parameter counts, PII, or property-health consequences | [ga4-collection-safety.md](references/02-execution/ga4-collection-safety.md) |
| Non-GA4 browser analytics destination | [analytics-vendors.md](references/02-execution/analytics-vendors.md) |
| Multiple streams, properties, accounts, pixels, brands, regions, hostnames, or environments | [multi-destination-routing.md](references/02-execution/multi-destination-routing.md) |
| Any browser media implementation | [media-tags.md](references/02-execution/media-tags.md) |
| Google Ads | [media-google-ads.md](references/02-execution/media-google-ads.md) |
| Floodlight or Campaign Manager 360 | [media-floodlight.md](references/02-execution/media-floodlight.md) |
| Microsoft Advertising or Bing Ads | [media-microsoft-ads.md](references/02-execution/media-microsoft-ads.md) |
| Meta Pixel | [media-meta.md](references/02-execution/media-meta.md) |
| TikTok Pixel | [media-tiktok.md](references/02-execution/media-tiktok.md) |
| Snap Pixel | [media-snapchat.md](references/02-execution/media-snapchat.md) |
| LinkedIn Insight Tag | [media-linkedin.md](references/02-execution/media-linkedin.md) |
| Pinterest Tag | [media-pinterest.md](references/02-execution/media-pinterest.md) |
| X Pixel | [media-x.md](references/02-execution/media-x.md) |
| Reddit Pixel | [media-reddit.md](references/02-execution/media-reddit.md) |
| Criteo OneTag | [media-criteo.md](references/02-execution/media-criteo.md) |
| Affiliate or partner-network browser tags | [media-affiliate.md](references/02-execution/media-affiliate.md) |
| CMP blocking or consent lifecycle | [cmp-consent.md](references/02-execution/cmp-consent.md) |
| OneTrust, Didomi, Axeptio, or another identified CMP implementation | [cmp-platform-patterns.md](references/02-execution/cmp-platform-patterns.md) |
| IAB TCF or Google Additional Consent is detected or requested | [tcf-consent.md](references/02-execution/tcf-consent.md) |
| Advanced, native, cookieless, anonymous, or limited-data consent | [vendor-consent-modes.md](references/02-execution/vendor-consent-modes.md) |
| Google basic or advanced Consent Mode | [google-consent-mode.md](references/02-execution/google-consent-mode.md) |
| First-party user data, enhanced conversions, or advanced matching | [first-party-data.md](references/02-execution/first-party-data.md) |
| dataLayer values, ecommerce arrays, runtime missing-data behavior, or transformations | [data-contract-and-transformations.md](references/02-execution/data-contract-and-transformations.md) |
| Repeated source-to-destination array projection, scalar validation, or transformation vectors | [transformation-patterns.md](references/02-execution/transformation-patterns.md) |
| Conversion Linker, click attribution, or cross-domain Google measurement | [conversion-linker-cross-domain.md](references/02-execution/conversion-linker-cross-domain.md) |
| Triggers, variables, SPA, firing settings, or sequencing | [triggers-and-variables.md](references/02-execution/triggers-and-variables.md) |
| Native, official, community, or custom templates | [template-governance.md](references/02-execution/template-governance.md) |
| MCP, API, export/import, or UI mutation | [tool-adapters.md](references/02-execution/tool-adapters.md) |
| Naming, folders, constants, lookup tables, regex tables, or reuse | [naming-and-reuse.md](references/02-execution/naming-and-reuse.md) |

## 03 - Judgement

Read [acceptance-and-handoff.md](references/03-judgement/acceptance-and-handoff.md) for every
configuration. Assign `Configured` only after authoritative workspace readback; otherwise use the
narrowest accurate status: `Partial`, `Blocked`, or `Deferred`.

## Core operational rules

- Treat a request to configure a named container as authorization to read it and create, update, or
  reuse the in-scope GTM objects in a dedicated workspace. Do not ask the user to choose a planning
  or read-only mode. Do not infer authority to delete unrelated objects, clean the container,
  publish, create a version, or change another system.
- Discover container, object-surface, template, destination, CMP, and source facts before asking
  questions. Finish safe discovery, then batch all remaining critical blockers in one request. Ask
  only for facts that cannot be established safely and block an actual configuration decision.
- Implement approved analytics event names, payload fields, literals, source mappings, filters, and
  business timing exactly. Do not optimize or redesign the tracking plan. Report current official
  documentation differences before mutation; preserve valid advisories and stop invalid, reserved,
  missing-required, incompatible, or unsupported requirements.
- Treat the explicit media brief as the media business authority. Use current official vendor
  documentation for the destination schema and use the tracking plan only for compatible source
  events and values. Never translate a media tag by analogy with GA4 or another vendor.
- Research the exact client-side product and inspect the installed template version, fields,
  permissions, defaults, and automatic behavior before designing its tags or transformations.
- Use a compatible native or installed supported template whenever one exists. Never replace a
  supported Google, Meta, Microsoft, or other product template with Custom HTML silently. If the
  required template cannot be installed or updated under current authority, mark the affected work
  `Blocked` instead of improvising a snippet.
- Classify the target as a web container and discover adapter capability per applicable object
  family. Configure built-in variables, Google tag configuration/destinations, Zones, environments,
  templates, or container settings only under their documented authority and risk boundary.
- Select the best-practice architecture from current official documentation, the applicable
  playbook, the installed template, the approved source values, and the consent requirement. Treat
  existing container state only as evidence for integration, consumers, conflicts, destinations,
  and conformant reuse; never as proof of best practice.
- Inspect only the objects related to the requested implementation. Reuse semantically compatible
  objects, reconcile an in-scope conflict when safely authorized, and never add a known duplicate or
  perform unrelated audit or cleanup work.
- Classify the request as greenfield or a delta against an existing related graph. For a delta,
  trace every affected consumer before renaming, changing shared parameters or triggers, repointing
  a destination, or pausing/unpausing a tag. Preserve unrelated objects; removal still requires
  explicit destructive authority.
- Default every in-scope analytics and media product to strict/basic CMP blocking. Detect the CMP and
  documented grant signal where possible; make unknown, undefined, uninitialized, and denied states
  block. Configure advanced/native denied-state behavior only after an explicit request and current
  product-specific proof.
- Build the smallest understandable object graph. Prefer direct DLVs, named constants for stable
  reusable values, settings variables for genuinely shared fields, LUTs/RLTs for real deterministic
  multi-scenario mappings, and narrow Custom JavaScript only for a required shape conversion.
- Follow the default naming convention unless the user supplied another clear convention. Preserve
  a coherent existing convention only as presentation. Create or reuse a shallow folder when
  several related objects benefit from grouping; never reorganize unrelated objects.
- Keep base/configuration tags from sending an automatic page view by default. Reconcile current
  automatic, partner, hard-coded, Enhanced Measurement, Event Builder, and SPA behavior before
  adding a manual page view or business event.
- Run the current official GA4 safety gate for names, requirements, limits, types, outgoing field
  counts, and PII. Report advisories, stop invalid requirements, and never silently truncate,
  coerce, remove, or enrich approved analytics fields.
- Resolve multi-destination and environment routing explicitly. Never make production a lookup
  default or let test traffic, first-party data, or incompatible consent leak to another destination.
- Preserve every required ecommerce item and exact vendor shape. Never assume the analytics item ID
  is the media catalog ID, silently drop an item, invent a fallback, or treat an empty
  transformation as a firing gate. Configure the approved business event and direct field mappings
  even though a runtime value can be absent. Do not create payload-eligibility CJS variables or
  validity triggers merely to suppress such sends; record the site/dataLayer dependency for runtime
  recette. Add a firing condition only when the explicit brief or current product documentation
  requires it, preferring a native trigger condition and using CJS only when unavoidable.
- Use a dedicated workspace. Build dependencies before consumers, use stable IDs and fingerprints,
  re-read every saved object, compare intended and stored fields, confirm all references, and ensure
  an identical rerun creates no duplicate or repeated update.
- Record external site, CMP, GA4-property, advertising-platform, catalog/feed, and publication work
  separately. Never claim that a GTM mutation completed another system's configuration.
- For Google products under the default strict/basic route, prove both pre-grant blocking and
  ownership of current Consent Mode defaults/updates for every applicable consent type. Do not
  confuse built-in behavior, Additional Consent Checks, or a custom-template consent API.
- If a critical requirement or mutation path is unavailable, mark the affected work `Blocked`; do
  not convert the run into a specification workflow. Preserve and report any exact partial saved
  state. Never require or claim runtime Preview, browser, network, CMP-journey, or vendor-platform
  validation, and never publish or create a GTM version.
- Keep server-side GTM, Conversions API, and browser/server deduplication architecture as future
  extensions. Never invent or generate a browser event ID. An explicitly briefed, approved
  browser-supplied `event_id` may be mapped when current browser documentation and the installed
  template support it; record the server/deduplication design separately as deferred.
