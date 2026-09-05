---
name: configure-gtm
description: "Operationally configure authorized Google Tag Manager web containers, server containers, or a connected web-to-server tagging pipeline for expert web analysts. Convert approved analytics requirements and explicit media briefs into clean, technically correct, consent-controlled saved GTM object graphs; preserve approved semantics, use live official documentation and inspected template capabilities, apply basic CMP/vendor control by default and advanced/native consent only when explicitly requested, verify every saved target, and never publish. Use for actual GTM mutation through MCP, API, export/import, or signed-in UI. Do not use for tracking-plan design, general audit/cleanup, site/dataLayer or cloud tagging-server development, legal decisions, runtime recette/certification, external vendor API coding, publication, or version creation."
---

# Configure Google Tag Manager

Operationally implement an approved analytics tracking plan and an explicit media implementation brief across authorized
GTM web and associated server workspaces. Treat the saved, readback-verified object graph for every
authorized target—and, for a pipeline, their statically verified sender/Client/Event Data/consumer
relationships—as the unit of success. A plan, prose specification, or one-sided pipeline is not
configuration. Never publish, create a version, or claim runtime certification.

When the input is a `ga4-tracking-plan` delivery directory, run
`python scripts/import_ga4_tracking_plan_handoff.py DELIVERY -o approved-semantics.json` first.
The importer verifies approval and hashes while preserving stable requirement identity.

## 01 - Orientation

Read [utility-contract.md](references/01-orientation/utility-contract.md) at the start. Read
[official-source-policy.md](references/01-orientation/official-source-policy.md) when beginning live
product, template, CMP, Client, Transformation, or destination research.

Classify the run before loading conditional detail:

- `web`: only authorized web-container workspaces.
- `server`: only authorized server-container workspaces; a discovered endpoint never grants access.
- `pipeline`: at least one authorized web sender and one authorized server receiver, modeled as a
  graph. Several senders may feed one claiming Client and one Event Data event may fan out.

## 02 - Execution

Read [implementation-workflow.md](references/02-execution/implementation-workflow.md) for every run.
Before mutation, use [configuration-contract.md](references/02-execution/configuration-contract.md).
For durable state and deterministic materialization, use
[configuration-run-and-resume.md](references/02-execution/configuration-run-and-resume.md), the
[configuration contract schema](schemas/configuration-contract.schema.json), the
[configuration run schema](schemas/configuration-run.schema.json).
Treat the JSON Schemas as structural/editor aids; the packaged contract and run validators are the
authoritative semantic gates and must pass before mutation or finalization.

### Shared and web routes

| Requirement | Read |
| --- | --- |
| Web object families, built-ins, Google destinations, Zones, environments, settings | [client-side-object-surface.md](references/02-execution/client-side-object-surface.md) |
| Tracking plan, exact analytics requirements, conformance | [tracking-plan-fidelity-and-conformance.md](references/02-execution/tracking-plan-fidelity-and-conformance.md) |
| Tracking refonte plus client inventory | [tracking-refonte.md](references/02-execution/tracking-refonte.md) |
| Google tag or GA4 | [analytics-tags.md](references/02-execution/analytics-tags.md) |
| Google field/settings/page-view ownership | [google-field-ownership.md](references/02-execution/google-field-ownership.md) |
| GA4 validity, limits, reserved names, PII | [ga4-collection-safety.md](references/02-execution/ga4-collection-safety.md) |
| Non-GA4 web analytics | [analytics-vendors.md](references/02-execution/analytics-vendors.md) |
| Multiple destinations, brands, hosts, environments | [multi-destination-routing.md](references/02-execution/multi-destination-routing.md) |
| Browser media architecture | [media-tags.md](references/02-execution/media-tags.md) |
| Google Ads | [media-google-ads.md](references/02-execution/media-google-ads.md) |
| Floodlight | [media-floodlight.md](references/02-execution/media-floodlight.md) |
| Microsoft Advertising | [media-microsoft-ads.md](references/02-execution/media-microsoft-ads.md) |
| Meta | [media-meta.md](references/02-execution/media-meta.md) |
| TikTok | [media-tiktok.md](references/02-execution/media-tiktok.md) |
| Snap | [media-snapchat.md](references/02-execution/media-snapchat.md) |
| LinkedIn | [media-linkedin.md](references/02-execution/media-linkedin.md) |
| Pinterest | [media-pinterest.md](references/02-execution/media-pinterest.md) |
| X | [media-x.md](references/02-execution/media-x.md) |
| Reddit | [media-reddit.md](references/02-execution/media-reddit.md) |
| Criteo | [media-criteo.md](references/02-execution/media-criteo.md) |
| Affiliate/partner | [media-affiliate.md](references/02-execution/media-affiliate.md) |
| CMP lifecycle and blocks | [cmp-consent.md](references/02-execution/cmp-consent.md) |
| OneTrust, Didomi, Axeptio, discovered CMP | [cmp-platform-patterns.md](references/02-execution/cmp-platform-patterns.md) |
| TCF / Additional Consent | [tcf-consent.md](references/02-execution/tcf-consent.md) |
| Advanced/native product consent | [vendor-consent-modes.md](references/02-execution/vendor-consent-modes.md) |
| Google Consent Mode | [google-consent-mode.md](references/02-execution/google-consent-mode.md) |
| First-party user data and enhanced matching | [first-party-data.md](references/02-execution/first-party-data.md) |
| dataLayer, ecommerce, shapes, missing values | [data-contract-and-transformations.md](references/02-execution/data-contract-and-transformations.md) |
| Repeated projections and transformations | [transformation-patterns.md](references/02-execution/transformation-patterns.md) |
| Conversion Linker or cross-domain | [conversion-linker-cross-domain.md](references/02-execution/conversion-linker-cross-domain.md) |
| Triggers, variables, SPA, sequencing | [triggers-and-variables.md](references/02-execution/triggers-and-variables.md) |
| Template selection and permissions | [template-governance.md](references/02-execution/template-governance.md) |
| MCP, API, export/import, UI | [tool-adapters.md](references/02-execution/tool-adapters.md) |
| Naming, folders, constants, LUT/RLT, reuse | [naming-and-reuse.md](references/02-execution/naming-and-reuse.md) |

### Pipeline route

For `pipeline`, read all three:

- [architecture-and-workflow.md](references/02-execution/pipeline/architecture-and-workflow.md)
- [transport-data-contract.md](references/02-execution/pipeline/transport-data-contract.md)
- [browser-server-deduplication.md](references/02-execution/pipeline/browser-server-deduplication.md)

### Server route

For `server` or `pipeline`, first read the shared server files:

- [object-surface-and-ingress.md](references/02-execution/server/object-surface-and-ingress.md)
- [tags-triggers-and-variables.md](references/02-execution/server/tags-triggers-and-variables.md)
- [consent-and-data-governance.md](references/02-execution/server/consent-and-data-governance.md)
- [transformations.md](references/02-execution/server/transformations.md)
- [first-party-data-and-secrets.md](references/02-execution/server/first-party-data-and-secrets.md)
- [media-destinations.md](references/02-execution/server/media-destinations.md)

Then load only the destination files that apply:

| Destination | Read |
| --- | --- |
| GA4 | [analytics-ga4.md](references/02-execution/server/analytics-ga4.md) |
| Other analytics | [analytics-vendors.md](references/02-execution/server/analytics-vendors.md) |
| Google Ads | [media-google-ads.md](references/02-execution/server/media-google-ads.md) |
| Floodlight | [media-floodlight.md](references/02-execution/server/media-floodlight.md) |
| Microsoft | [media-microsoft-ads.md](references/02-execution/server/media-microsoft-ads.md) |
| Meta | [media-meta.md](references/02-execution/server/media-meta.md) |
| TikTok | [media-tiktok.md](references/02-execution/server/media-tiktok.md) |
| Snap | [media-snapchat.md](references/02-execution/server/media-snapchat.md) |
| LinkedIn | [media-linkedin.md](references/02-execution/server/media-linkedin.md) |
| Pinterest | [media-pinterest.md](references/02-execution/server/media-pinterest.md) |
| X | [media-x.md](references/02-execution/server/media-x.md) |
| Reddit | [media-reddit.md](references/02-execution/server/media-reddit.md) |
| Criteo | [media-criteo.md](references/02-execution/server/media-criteo.md) |
| Affiliate/partner | [media-affiliate.md](references/02-execution/server/media-affiliate.md) |

## 03 - Judgement

Before assigning status, read
[acceptance-and-handoff.md](references/03-judgement/acceptance-and-handoff.md). Use `Configured` only
after authoritative readback of every required target, static cross-target proof, and an identical
rerun no-op. Otherwise use the narrowest accurate `Partial`, `Blocked`, or `Deferred` result.

## Web invariants

Operationally implement an approved analytics tracking plan and an explicit media implementation
brief as a saved, verified GTM object graph, whether the request is greenfield or a delta. Preserve
the complete supported client-side surface: tags, normal and blocking triggers, variables, folders,
templates, Google tag configuration/destinations, workspaces, Zones, environments, and settings.

Default every product to strict/basic CMP blocking on its web route unless an explicit current
advanced/native contract applies. Inspect the installed template, and use a native or supported
template whenever one exists. Inspect only the objects related to the requested implementation
unless an authorized refonte requires the complete inventory. Container prevalence is integration
evidence, never as proof of best practice.

Use direct mappings first, constants/settings for real reuse, LUT/RLT for deterministic routing,
and CJS only for a required shape conversion. Keep a shallow folder structure. Do not create
payload-eligibility variables, validity triggers, speculative helpers, or browser Custom HTML when
the supported template owns the behavior. Measurement Protocol, mobile, CRM, offline, and
arbitrary backend ingress remain future extensions.

Setup/cleanup-only tags without ordinary firing triggers are outside the current executable
topology. Inspect existing sequences for impact, but hold a requirement needing that unsupported
path; never add dummy triggers or claim setup-only field-test coverage. See the triggers reference.

## Operational rules

- A named-target configuration request authorizes routine create/update/reuse only inside that
  target's dedicated workspace. Web authority does not grant server authority or vice versa.
- Use current official documentation and inspected installed-template fields, permissions, network
  hosts, defaults, and automatic behavior. A media brief controls business intent; a tracking plan
  never becomes another vendor's schema by analogy.
- Preserve valid approved analytics event names, fields, sources, literals, filters, and timing.
  Select best-practice architecture before reuse; container prevalence is integration evidence.
- For web tags, preserve the strict/basic CMP default: baseline tags use a verified CMP lifecycle
  event plus the vendor block; business tags use their business trigger plus the block. Do not stack
  an equivalent Additional Consent Check. Advanced/native behavior remains explicit-only.
- In every new contract 7.0 / run 4.0 web or pipeline run, bind each executing web tag to one contract-owned
  execution topology, bind every page-view-capable destination to one effective owner and
  `send_page_view` decision, bind `user_data`/`user_id` to an explicit first-party route, and keep
  ordered inventory dispositions for a refonte. These controls may not disappear during
  client/server materialization.
- For a pipeline, configure and read back the receiver graph before changing a live sender endpoint.
  Every pipeline names its transport owner as the mandatory high-impact cutover operation, including
  a new sender route. That operation depends on every required Client, Event Data, Transformation,
  trigger, and destination operation. One failed dependency stops its transitive dependents, not
  independent safe subtrees.
- Record one consent topology per destination. Google Consent Mode is set in the web container and
  carried to consent-aware server Google tags. For non-Google server gating, prove the approved
  signal on every triggering event and fail unknown state closed unless policy says otherwise.
  Distinguish incoming Google-native consent, template-native consent, a supported Additional
  Consent Check, a server blocking trigger, and no server gate. A direct browser destination keeps
  its vendor block. Resolve browser-to-server collection policy separately from downstream vendor
  eligibility. A shared transporter does not mechanically inherit each destination's block; an
  approved unblocked carrier transports documented consent on every applicable event. Google-native
  denied-state behavior is not a strict no-request gate, and advanced behavior requires explicit
  approval. Use the approved blocked-transport design when browser collection itself must wait.
- Resolve each transported field across source, web variable, wire, claiming Client, Event Data,
  server owner, template field, destination type, missing behavior, and runtime verification note. `items` is an array and `user_data` is an object; never encode a universal "two arrays" rule. Prove every
  non-scalar shape and never silently flatten, stringify, truncate, or drop items.
- Use native automatic mapping, direct Event Data, a template mapping table, or a narrow supported
  variable before a scoped Transformation. Broad shared Transformations, Client claim changes,
  template permission expansion, deletion/replacement, settings changes, and live endpoint cutover
  require their explicit high-impact authority.
- Record a dedup contract only when the same destination occurrence can arrive twice. A
  dual-delivery purchase requires a stable product-supported transaction/order/occurrence identity;
  other dual-delivery events require an approved stable occurrence ID. If none exists, choose one
  delivery channel or keep the overlap blocked. Never synthesize an identity from GTM internals,
  regenerate the ID server-side, or impose `event_id` on another product.
- Keep first-party data event- and consumer-scoped. Record normalization/hash ownership and consent.
  Never persist raw PII or credentials. Resolve secrets only through secure ephemeral input, redact
  before any artifact write, and never treat two redacted markers as equality proof.
- Let the validated contract materialize active run sections. The authenticated adapter runtime
  captures, retains, and fingerprints the redacted canonical target graph and workspace changes
  before mutation; never accept caller-authored baseline evidence. Adapters populate readbacks,
  journals, and results; finalization derives status and the human/machine result. Never edit
  active run state by hand or retry an ambiguous write before authoritative readback.
- Bind every mutation to at least one approved requirement and a traceable approval record from
  its approved-input locator. Hashes detect inconsistent edits; establish actual authority from the
  user's instructions and source material, and recheck scope after a changed payload. Official documentation
  establishes current product mechanics, never mutation authority. Reject any tag
  or native User-Provided Data variable that configures `user_data` or `user_id` without a complete
  first-party-data route. Before changing a shared Google Configuration Settings variable, close
  over every authenticated baseline tag that references it.
- Require action-specific authority and state: all deltas carry object ID plus pre-change state;
  rename, replace, template mutation, and remove carry their extra governed fields. Verify removal
  by authoritative absence. A reopened failure discards stale comparison/readback evidence.
- Publication sequence is external: server publish → server recette → web cutover publish → web and
  end-to-end recette. Open publication dependencies do not make a saved, verified setup `Blocked`.
- Keep cloud tagging-server provisioning, DNS/CDN, website/dataLayer work, external API coding,
  platform administration, runtime Preview, legal decisions, publication, and version creation
  external.
