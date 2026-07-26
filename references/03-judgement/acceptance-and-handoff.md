# Operational acceptance and handoff

## Contents

- [Configured means saved and verified](#configured-means-saved-and-verified)
- [Operational statuses](#operational-statuses)
- [Configuration judgement matrix](#configuration-judgement-matrix)
- [Analytics conformance proof](#analytics-conformance-proof)
- [Consent configuration proof](#consent-configuration-proof)
- [Concise handoff](#concise-handoff)

## Configured means saved and verified

Assign `Configured` only when authoritative current-workspace readback proves that the complete
in-scope GTM object graph already matched or now matches the approved requirement. Require every
applicable condition:

1. Resolve the target account, web container, environment, and dedicated workspace by stable ID;
   record conflicts and pre-existing workspace changes.
2. Use the approved tracking plan or exact direct analytics decision for analytics, the explicit
   human media brief for media, and basic CMP blocking unless an advanced route was requested.
3. Open current official documentation and inspect the installed template version before designing
   event fields, transformations, consent, or automatic behavior.
4. Inspect only relevant existing tags, triggers, variables, templates, folders, consumers,
   destinations, consent paths, automatic behavior, and duplicate/conflict risks.
   Include required built-ins, Google tag configurations, and any relevant Zone, environment, or
   container-setting restriction.
5. Select the best-practice architecture before considering container reuse. Reuse only a
   semantically compatible object; do not copy legacy architecture or add a known duplicate.
6. Resolve every outgoing field from approved source to GTM variable to installed-template field to
   official destination contract. Preserve zero/false and reject invented values.
7. Preserve every approved array item and map runtime values directly. Do not add a speculative
   payload-validity/eligibility helper; record runtime missing data as a site/dataLayer and recette
   dependency.
8. Use clear naming and a shallow folder when several related objects benefit. Use DLVs, constants,
   settings variables, LUTs/RLTs, and CJS according to the least-complex mapping order.
9. Prove a valid normal trigger, firing option, initialization path, and basic block or explicitly
   approved advanced consent route for every tag.
10. Reconcile known automatic/manual event, page-view, shared-execution-unit, environment, and
    destination conflicts.
11. Re-read every created, updated, and reused object; compare intended and saved fields,
    references, consumers, template version, folder, consent, and fingerprints.
12. Prove the current authority boundary, current official-source manifest, exact analytics approved-to-
    saved conformance, and media brief/official-schema mapping.
13. Recompute the object graph so an identical rerun is entirely `reuse` or `untouched`.
14. Distinguish pre-existing workspace changes from current-run writes and final workspace totals.
15. Record external dependencies and confirm that no runtime recette, publication, Submit, or GTM
    version action occurred.

Static configuration verification is not observed browser, network, CMP, or vendor-platform
behavior. Runtime recette and publication remain separate workflows.

## Operational statuses

Use one status per independent requirement or tag family:

| Status | Meaning |
| --- | --- |
| `Configured` | Authoritative saved-workspace readback satisfies the complete configuration and all applicable invariants. No write is required when it already matched. |
| `Partial` | The current run saved some in-scope objects but stopped before completing their dependent graph; exact saved state and safe recovery boundary are recorded. |
| `Blocked` | A critical business, source, destination, template, consent, conflict, access, or mutation fact prevents configuration. No planning/specification status substitutes for the operational result. |
| `Deferred` | The requirement belongs to intentionally future server-side GTM, CAPI, or browser/server deduplication. An explicitly supplied browser `event_id` can still be configured under the browser-field rule. |

Apply mixed statuses at requirement/tag-family grain so one blocked family does not mislabel an
independent configured family.

## Configuration judgement matrix

Use every applicable row; load the detailed playbook for the selected requirement.

| Requirement or trap | Required saved-configuration judgement |
| --- | --- |
| Approved analytics event | Exact event, source event, timing, filter, outgoing fields, sources, literals, and item scope match the plan. |
| Valid custom analytics event with a recommended alternative | Preserve the approved event, report the advisory, and do not substitute or enrich it. |
| Invalid/reserved event or missing required analytics field | Block only the affected requirement; never invent or substitute a value/event. |
| Recommended/optional field absent from plan | Keep it absent; documentation is not payload authorization. |
| Multi-part tracking plan | Resolve only relevant included/reference/excluded/ambiguous parts; hidden and visible status alone decides nothing. |
| GA4 configuration | Measurement ID reference, connected destinations, settings variables, consent, and explicit page-view behavior are correct. |
| Google tag and destinations | `GT-`, `G-`, and `AW-` identities, executable tag, connected destinations, GA4 event target, inherited settings, consumers, and consent routes are not conflated. |
| GA4 collection safety | Current official name, reserved, required, type, limit, final outgoing-count, item-scope, and PII checks pass with no silent truncation, coercion, or enrichment. |
| Native GA4 ecommerce | Current native ecommerce setting uses the approved Data Layer or Custom Object source; direct mappings or a narrow real shape transform replace speculative validity guards. |
| Enhanced Measurement overlap | Confirmed automatic scroll, outbound-click, search, video, download, form, page-view, and history ownership does not duplicate the approved manual event. |
| GA4 lifecycle fields | `user_id`, user properties/content groups, `traffic_type`, and `debug_mode` have explicit source, scope, lifecycle, reset/omission, consumers, and external Admin dependencies. |
| Non-GA4 analytics | Approved semantics, current official browser schema, installed template, base/event behavior, consent, and external property work remain distinct. |
| Manual page view or SPA | Reconcile Google tag, Enhanced Measurement, initial/history/application events, retained values, consent timing, and duplicate paths. |
| GA4 external administration | Keep custom definitions, key events, data-stream, cross-domain, and other property settings outside the GTM completion claim. |
| Media brief | Platform, business action/use, destination identity, official browser event/schema, installed template, and source mapping are explicit. |
| Media event absent from analytics plan | Configure from the media brief and official schema; use the plan only for compatible source evidence. |
| Informal media label | Block until the official event/conversion and destination identity are established. |
| Existing initialization | Reuse one compatible GTM/site/plugin/partner path or create one required base tag; do not add a speculative duplicate. |
| Google Ads conversion | Conversion ID/label, direct-versus-imported architecture, value/currency, transaction ID, action dependency, trigger, and consent are explicit. |
| Google Ads remarketing | Current business vertical/feed contract and every required item replace any unmodified GA4-array assumption. |
| Conversion Linker | Create/reuse only after current Google tag architecture, consumers, cross-domain need, and existing helpers are checked. |
| Multi-destination routing | Every selector and no-match case routes to the approved identity; production is not the fallback and test traffic cannot leak. |
| Floodlight | Configuration/activity identities, counter/sales contract, custom variables, Google tag/linker, consent, and external platform dependencies are explicit. |
| Microsoft UET | Base/page-load behavior, custom-event fields, goal dependency, SPA option, and UET consent route remain distinct. |
| Meta ecommerce | Current browser `content_ids`/`contents` contracts, catalog ID, value/currency, every item, and installed supported-template fields are explicit. |
| TikTok event | Current standard/custom event, objective fields, catalog, Event Builder/automatic overlap, template, and consent are explicit. |
| Snap event | Current browser Pixel/template documentation—not CAPI or another vendor—establishes fields, items, matching, and consent. |
| LinkedIn, Pinterest, X, Reddit, or Criteo | Exact current browser product, destination identity, base/event or page-type architecture, installed template, source mapping, consent, and platform dependencies are explicit. |
| Affiliate network | Exact program/advertiser, base/journey path, conversion and basket schema, transaction/reference duplicate control, supported template, consent, and platform dependencies are explicit. |
| Unlisted media vendor | Current official browser event, field, template, consent, and matching documentation establishes every critical decision. |
| Required media source missing at design time | Block the affected configuration; no value or source is guessed. |
| Mapped media value absent at runtime | Keep the direct approved mapping and record a site/dataLayer and recette dependency; do not create a generic payload gate. |
| Browser/server field boundary | Browser Pixel/tag fields come from current browser documentation/template; CAPI/server-only fields are not copied into the client tag. |
| Multi-item transformation | Representative missing/empty/one/many/zero/invalid cases prove deterministic shape and item preservation; no row is silently filtered and no separate validity gate is added. |
| Catalog/feed ID | The actual catalog convention is approved; analytics item IDs are not assumed equivalent. |
| Direct source mapping | Use a DLV/direct field rather than an unnecessary transformation. |
| LUT/RLT | Multiple real deterministic inputs, clear mapping, and safe no-match behavior justify it. |
| Custom JavaScript | Built-ins cannot express the required output; the function is narrow, deterministic, null-safe, type-explicit, and side-effect free. |
| Payload firing | The approved business event controls firing. A native extra condition exists only when the explicit brief or current destination documentation requires it. |
| DLV version | Version 1 literal-dot or Version 2 nested-path semantics match the source and all consumers. |
| Trigger Boolean logic | Firing-trigger OR, row-level AND, exception precedence, regex intent, repeatability, and event scope are correct. |
| Tag advanced settings | Priority, schedule, live-only, pause state, firing option, sequencing, and failure behavior remain default unless required. |
| Tag sequencing | The initiating tag carries the full consent predicate because sequenced tags ignore their own firing/exception triggers. |
| Default basic consent | Every in-scope base/event path is ineligible while the exact CMP state is unknown, uninitialized, or denied. |
| Basic Google consent | One confirmed owner sets/updates applicable `analytics_storage`, `ad_storage`, `ad_user_data`, and `ad_personalization`; strict pre-grant blocks and built-in checks remain distinct. |
| CMP block scope | Each exception can match every GTM event used by its consumers; a CMP-only event matcher does not block unrelated business events. |
| Compound CMP predicate | Independent category/purpose/vendor/product grants use the smallest OR-denial block set; no mutually exclusive AND or speculative consent helper. |
| Advanced consent | Exact product, explicit request, official denied-state behavior, defaults/updates, CMP/template support, user-data limits, and absence of a defeating block are proven. |
| Advanced Google options | `region`, `wait_for_update`, `ads_data_redaction`, `url_passthrough`, linker, and cross-domain behavior exist only when explicitly required and documented. |
| TCF 2.3 | Only an applicable approved TCF route configures current TC/Additional Consent plumbing; legal bases, purposes, vendors, restrictions, and CMP certification remain client/CMP authority. |
| Shared Google execution unit | Every destination has a compatible route or an approved officially supported separation; incompatible policies are blocked. |
| First-party user data | Explicit request, controlled source, accepted fields, normalization/hash ownership, consent, destination isolation, and no PII leakage are proven. |
| First-party Google data | Exact GA4/Ads feature, native User-Provided Data/template field, raw versus pre-hashed mode, hashing owner, Google consent signals, and account-side dependency are explicit. |
| Template | A native or supported template is used first. Identity/version, publisher, permissions, fields/defaults, consumers, automatic behavior, and any approved install/update are verified before and after mutation; unavailable authority blocks rather than triggering silent Custom HTML. |
| Complete web object surface | Every relevant tag, trigger, user-defined/built-in variable, folder, template, Google tag config/destination, Zone, environment, and container setting is configured, reused, intentionally untouched, or blocked under the correct authority. |
| Naming and folder | Default or approved convention is clear; related objects are grouped shallowly where useful and unrelated objects remain untouched. |
| Existing-object reuse | Output, ownership, source, shape, timing, consent, consumers, template, environment, and future change path are compatible. |
| Delta/change request | Every update, rename, fanout, trigger/destination change, pause/unpause, or authorized remove traces consumers and pre-change state; a greenfield request does not overwrite by name and a no-op rerun performs no mutation. |
| Known conflicting implementation | Reconcile within in-scope authority or block; never add a parallel duplicate or silently disable unrelated collection. |
| Workspace and adapter | Dedicated workspace, pagination, stable IDs, fingerprints, pre-change state, conflicts, exact actions, and saved readback are complete. |
| Uncertain write or partial failure | Read back before retrying; stop dependent writes and preserve the exact current-operation recovery boundary. |
| Idempotent rerun | Every completed row resolves to `reuse` or `untouched`, never another create or repeat update. |
| Mutation unavailable | Status is `Blocked`, no live-change claim is made, and the exact access/capability needed is stated. |
| Browser event ID | Never generate one. Preserve an explicitly supplied approved browser `event_id` only when current browser documentation and the installed template support it; server matching/deduplication stays `Deferred`. |
| Server-side/deduplication request | Keep independent client-side work judgeable and mark the future capability `Deferred`; do not design the server/CAPI route. |

## Analytics conformance proof

Before the first analytics write and again after saved readback, record the concise result for:

- expected and actual requirement IDs;
- included/reference-only/excluded scope differences;
- event, source event, timing, filters, outgoing fields, source paths, literals, and type/shape;
- unauthorized additions, removals, substitutions, and hidden-scope inclusions;
- blocking errors, advisories, implementation notes, and explicit amendments.

Use `scripts/validate_contract_conformance.py` when normalized JSON is available. It proves equality,
not workbook interpretation or official semantics. Keep technical GTM infrastructure outside the
analytics payload comparison and verify it through saved-object readback.

## Consent configuration proof

For basic gating, derive configured eligibility for CMP uninitialized/undefined, denied, another
vendor granted, complete grant, later grant, repeatable readiness/change, and revocation. Record the
normal trigger, block(s), predicate, event scope, and firing option responsible. Remember that a GTM
block cannot unload a script already loaded after grant.

For an explicitly approved advanced route, record the exact product/feature, defaults, updates,
returning choice, revocation, denied-state load/request/storage/data behavior, template/CMP support,
user-data restrictions, and absence of a conflicting block. Label it accurately as
`advanced consent-aware`, `native stop/hold`, `native cookie-control`, or
`adaptive/anonymous analytics`; do not collapse all behavior into “consent gated.”

Complete this static truth table for every consent route; add rows only when the actual CMP/product
has another material configured state:

| State | Expected saved eligibility/behavior | Controlling GTM mechanism | Evidence |
| --- | --- | --- | --- |
| CMP uninitialized/undefined | Basic route blocked; advanced route follows its explicit documented default. | Exact default, block, or additional-consent setting | Saved CMP/tag/trigger fields and official source |
| Required grant denied | Basic route blocked; advanced/native route uses only approved documented denied-state behavior. | Predicate or product consent setting | Saved fields and source manifest |
| Unrelated vendor/category granted | Still blocked when another required grant is missing. | OR-denial block set | Saved predicates and consumers |
| Complete grant before event | Normal event is eligible once. | Normal trigger plus consent route | Saved trigger graph |
| Grant after an earlier blocked event | Only the approved late-grant initialization/event policy is eligible. | Readiness/change trigger and firing option | Saved lifecycle fields |
| Repeated readiness/change | No duplicate initialization or business event beyond approved repeatability. | Trigger/firing option | Saved trigger graph |
| Revocation | Future basic events block; no unsupported unload guarantee. | Updated CMP state and blocks | Saved predicates and documented limitation |

These are saved-configuration expectations, never runtime observations.

## Concise handoff

Return one compact manifest that the recette analyst can use without reconstructing the saved
graph:

| Manifest field | Required content |
| --- | --- |
| Target | Account, container, environment, dedicated workspace, and saved-state timestamp. |
| Requirement | Requirement/tag-family ID, status, approved source event/action, destination identity, and selected consent route. |
| Saved graph | Created/updated/renamed/paused/unpaused/reused/untouched/removed object names plus stable IDs and semantic trigger/folder/sequencing references. |
| Expected execution | Normal trigger, firing option, base/config dependency, block/additional checks, and concise expected static behavior. |
| Payload map | Outgoing browser field, source path/literal, GTM variable/transform, template field, type/cardinality, and runtime missing-data dependency. |
| Recette cues | Representative event, expected tag, important resolved fields, known automatic/duplicate owner, and consent states to exercise. |
| Dependencies | Site/dataLayer, CMP, GA4/property, advertising platform, feed/catalog, template access, runtime recette, and publication owner. |
| Evidence | Approved input locator, current official-source manifest, saved-object readback, and exact partial recovery boundary when applicable. |

Also include only what the analyst needs to operate the workspace:

- target account, container, environment, and dedicated workspace;
- status by requirement/tag family;
- created, updated, reused, untouched, partial, blocked, and deferred in-scope objects;
- pre-existing workspace changes, current-run writes, and final totals;
- exact analytics conformance result or media brief/official-schema mapping result;
- approved-input versus implementation-decision provenance and the concise official-source manifest;
- material documentation advisories and blocking errors;
- selected consent route and any important configured limitation;
- completed consent truth table and multi-destination routing result when applicable;
- applicable client-side object families, including intentionally untouched or separately
  authorized high-impact objects;
- exact partial recovery boundary or access blocker;
- external site, CMP, GA4-property, advertising-platform, catalog/feed, and publication dependencies;
- confirmation that an identical rerun is a no-op for configured work;
- confirmation that runtime recette and publication were not performed.

Do not duplicate a large technical annex by default. Preserve detailed object IDs, fingerprints,
pre-change representations, official sources, and static vectors in the current-operation evidence
when they are needed for safe recovery or review.
