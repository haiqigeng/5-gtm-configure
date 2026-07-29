# Changelog

## 5.1.0

### Why This Release Matters

- Prevents an approved first-party identifier or matching feature from being interpreted as
  permission to attach `user_data` to every analytics event.
- Makes the choice between direct Google tag fields, Configuration Settings variables, native
  User-Provided Data variables, and conversion-specific fields explicit and proportional.

### What Changed

- Require the exact destination feature, collection mode, authorized consuming tags/pages/events,
  source timing and lifetime, consent route, account dependency, and owning GTM object before
  configuring first-party data.
- Configure `user_id` directly on its sole consuming Google tag. Use a Configuration Settings
  variable only when the same source, lifecycle, reset behavior, consent, and consumer contract is
  genuinely reused by multiple compatible Google tags.
- Route GA4 user-provided data through the native User-Provided Data variable on only the
  authorized GA4 Event tags. Keep tag-wide Google Ads collection and event-specific enhanced
  conversions under their separately approved current native routes.
- Separate GA4 `user_id`, GA4 user-provided data, GA4 user properties, and destination-specific
  advertising matching in the implementation and acceptance contracts.
- Add current official GA4 user-provided-data and User-ID documentation entry points plus a
  deterministic narrow-consumer-scope regression scenario.
- Derive the release checker's required reference inventory from the canonical reference-layer
  map, tolerate ignored development caches, and stop release tests from deleting repository
  caches.
- Remove redundant high-impact-object matching logic and make the configuration-validator CLI use
  its canonical contract loader.

### What Users Should Do

- State the exact first-party-data feature and whether collection is tag-wide, event-specific, or
  conversion-specific, including every authorized consumer.
- Prefer a direct tag field for one consumer and introduce a shared settings variable only when
  there is a real compatible multi-tag reuse contract.

### Validation

- Add contract coverage for narrow first-party consumer scope and normalized high-impact GTM
  object names.
- Pass all 81 unit tests, skill and release validation, Ruff formatting/lint, deterministic
  runtime packaging, and whitespace checks for `v5.1.0`.

### Known Limits

- First-party-data features remain explicit opt-in configuration. Client consent policy,
  account-side activation/terms, runtime data quality, and observed transmission remain external
  responsibilities.
- This release does not add server-side GTM, offline uploads, Conversions API, or browser/server
  deduplication.

## 5.0.0

### Why This Release Matters

- Prioritizes practical analyst utility: the skill now configures the documented browser event and
  fields directly instead of adding speculative payload-eligibility machinery.
- Makes supported templates, current browser schemas, complete Google/GA4 mechanics, and safe delta
  operations enforceable parts of the saved-configuration contract.

### What Changed

- Require native or supported templates first for media products. Missing template
  installation/update authority now blocks the affected family instead of silently falling back to
  Custom HTML.
- Separate design-time mapping completeness from runtime data quality. Remove routine
  `CJS - ... Eligible` and validity-trigger patterns; preserve direct business-event firing and
  record runtime missing data for site/dataLayer ownership and recette.
- Add browser-specific media field matrices that exclude server/CAPI-only parameters, preserve an
  explicitly supplied documented browser `event_id`, and never generate event IDs or server
  deduplication architecture.
- Expand GA4 configuration with Google tag/destination identity (`GT-`, `G-`, `AW-`), native
  ecommerce sources, Enhanced Measurement collision handling, `user_id` lifecycle, user
  properties/content groups, `traffic_type`, and explicit `debug_mode` behavior.
- Complete the basic Google Consent Mode route with strict pre-grant blocking, one verified
  defaults/updates owner, all applicable consent signals, and clear separation of built-in checks,
  Additional Consent Checks, triggers, and template APIs. Keep regional defaults,
  `wait_for_update`, redaction, URL passthrough, linker, and cross-domain options explicit-only.
- Add operational affiliate-network configuration and a conditional TCF 2.3/Additional Consent
  route without making legal-purpose, vendor, or CMP-certification decisions.
- Add native client-side first-party-data mechanics, including the User-Provided Data variable,
  raw/pre-hashed mode, hashing ownership, consent, and external account activation.
- Treat existing-container requests as greenfield or delta changes. Validate update, rename,
  pause/unpause, trigger/destination fanout, consumer impact, pre-change state, destructive
  authority, and idempotent no-op reruns.
- Expand web-trigger mechanics and DLV v1/v2 guidance, activate the generic non-GA4 analytics route,
  and correct the Piwik PRO GTM documentation entry point.
- Normalize returned trigger, block, folder, and tag-sequencing IDs to semantic references in the
  deterministic object-graph comparator.
- Consolidate status/completion definitions in the acceptance reference and add a compact
  recette-ready handoff manifest.

### What Users Should Do

- Supply the approved analytics contract or explicit media brief and destination identity; let the
  skill discover compatible existing objects and supported templates before filling only genuine
  blockers.
- Review the saved graph and recette-ready handoff, then use the separate Preview recette and
  publication workflows for runtime acceptance and release.

### Validation

- Add focused configuration, forward, utility, and semantic-graph cases for empty Meta/Microsoft
  ecommerce payloads, existing-object reuse, native GA4 purchase, complete basic Google consent,
  delta updates, Enhanced Measurement overlap, browser `event_id`, affiliate baskets, unlisted
  vendors, and returned-ID readback.
- Run release structure checks, the full unit suite, lint/format checks, compilation, deterministic
  package builds, and whitespace validation for `v5.0.0`.

### Known Limits

- The skill remains client-side GTM configuration only: it does not design tracking plans, develop
  site/dataLayer code, run runtime recette, publish, or create GTM versions.
- Server-side GTM, Conversions API, and browser/server deduplication remain deferred. Multi-container
  rollout orchestration is not introduced in this release.

## 4.0.1

### Why This Release Matters

- Synchronizes repository/package metadata, release checks, CI, contribution guidance, and README
  instructions with the current v4 client-side GTM configuration surface.
- Records the latest synthetic-test observations without changing the runtime skill contract.

### What Changed

- Align the package version, release checker, CI validation tag, contribution command, README
  release commands, and distributable package name at `4.0.1`.
- Add an explicit current-release statement to the README.
- Record payload-eligibility helpers, template selection, and browser-versus-server parameter
  mapping as future evaluation items; no related behavior or playbook rule is changed here.

### What Users Should Do

- Continue using the v4 client-side configuration workflow and review the saved-object handoff
  before any separate publication decision.
- Treat the recorded synthetic-test observations as pending future evaluation, not as changes to
  the current implementation policy.

### Validation

- Preserve the v4.0.0 runtime references, configuration contract, scenarios, and tests unchanged.
- Run the repository release checks, unit tests, lint/format checks, compilation, and deterministic
  package build for `v4.0.1`.

### Known Limits

- This is a documentation/repository synchronization release; it does not expand the client-side
  scope or change payload, template, consent, or firing behavior.
- Server-side GTM, Conversions API, browser/server deduplication, and event-ID architecture remain
  outside the current skill.

## 4.0.0

### Why This Release Matters

- Completes the skill's client-side north star in one release: configure the full applicable GTM
  web-container object graph for analytics and media work, not only the most common tag families.
- Expands practical expert coverage while retaining the v3 safety model: approved analytics
  semantics remain immutable, media intent still requires a human brief, strict/basic CMP blocking
  remains the default, all work stays in a saved workspace, and publication remains prohibited.
- Adds deterministic controls only where they prevent authority drift, silent payload enrichment,
  cross-destination leakage, unsafe high-impact changes, or false saved-state claims.

### What Changed

- Cover tags, normal and blocking triggers, user-defined and built-in variables, folders, templates,
  Google tag configuration/destinations, workspace controls, and relevant Zones, environments, and
  container settings. Zone/environment/destination movement, container-setting changes, and custom
  template code require separate explicit authority.
- Add a live-official-source GA4 safety gate for current names, reserved terms, collection limits,
  required types/shapes, automatic-event overlap, and PII/sensitive-data risk. Invalid requirements
  block without silent truncation, coercion, enrichment, removal, or substitution.
- Add first-class client-side playbooks for Floodlight, LinkedIn, Pinterest, X, Reddit, and Criteo,
  plus a generic official-first route for Matomo, Piwik PRO, Adobe, and other supported non-GA4
  analytics destinations.
- Add CMP-specific discovery and lifecycle patterns for OneTrust, Cookiebot, and Didomi while
  preserving product-level consent classification and fail-closed unknown/uninitialized handling.
- Add Conversion Linker/cross-domain ownership, multi-stream/account/pixel/brand/region/environment
  routing, safe no-match behavior, and shared-Google-destination reconciliation. Unknown routing
  can never default to a production destination.
- Add destination-isolated first-party-data ownership, deterministic source-to-destination
  transformation patterns, complete ecommerce item preservation, and required zero/one/many/
  invalid static vectors.
- Batch all unresolved critical questions after safe discovery instead of interrupting the run one
  field at a time. Record an official-source manifest and field-level authority/provenance.
- Introduce the strict `schema_version: "4.0"` configuration contract validator. It rejects
  implementation fields in business requirements, unapproved analytics fields, missing provenance,
  undocumented updates, destructive actions without authorization, and high-impact mutations
  without explicit authority.
- Add a read-only normalized object-graph comparator that ignores defined server metadata, retains
  material nested configuration, reports missing/extra/mismatched objects, and supports deterministic
  readback and no-op rerun proof.
- Package both new runtime controls with the existing analytics conformance comparator. Add golden
  object-graph cases and forward cases covering GA4 PII/enrichment, environment routing, Pinterest,
  Floodlight, OneTrust, Zones, Matomo, and cross-domain ownership.

### What Users Should Do

- Provide the target web container and approved analytics tracking plan or exact direct analytics
  requirements; add an explicit platform, business action, destination use, and identity for media.
- Provide high-impact authority only when the requested setup genuinely requires a Zone,
  environment, destination-link/movement, container setting, or custom-template-code change.
- Expect one consolidated blocker request after the skill has exhausted safe container, template,
  CMP, and official-documentation discovery.
- Preserve the v4 configuration contract, official-source manifest, object change journal,
  deterministic saved-state diff, and external-dependency list with the handoff.

### Validation

- Dependency-free unit tests protect v4 schema authority, field provenance, update pre-state,
  high-impact authorization, legacy opt-in, normalized metadata handling, duplicate identity
  rejection, semantic object equality, and deterministic archives.
- Contract tests protect the expanded object surface, GA4 safety, non-GA4 analytics, CMP platforms,
  cross-domain behavior, multi-destination isolation, the eleven first-class media families, and
  runtime packaging of all deterministic controls.
- Forward and golden fixtures exercise realistic source artifacts and expected controls without
  claiming browser, network, CMP, or vendor-platform runtime certification.

### Known Limits

- Static saved-state verification does not replace GTM Preview, Tag Assistant, browser/network/CMP
  recette, or vendor-platform receipt and attribution validation.
- Vendor schemas, collection limits, CMP signals, and template capabilities remain current official
  lookups; the skill intentionally does not freeze volatile catalogues.
- External GA4 Admin, ad-platform conversion/action creation, catalog/feed administration, and CMP
  policy decisions remain dependencies rather than GTM configuration claims.
- Publication, GTM version creation, deletion/general cleanup, site/dataLayer development,
  server-side GTM, CAPI, event-ID architecture, and browser/server deduplication remain outside v4.

## 3.0.0

### Why This Release Matters

- Reorients the skill around its operational north star: implement a clean,
  well-organized, technically correct, best-practice, consent-controlled setup
  in an actual client-side GTM workspace.
- Makes the saved, verified GTM object graph the unit of success. A plan or
  complete specification no longer substitutes for configuration.
- Preserves the existing analytics, media, consent, data, trigger, template,
  naming, adapter, conflict, and idempotency expertise while moving complexity
  out of mandatory process and into conditionally routed playbooks.

### What Changed

- Replace multiple planning/read-only/specification paths with one internal
  configuration loop: resolve blocking inputs, create/reuse the workspace,
  research official sources and installed templates, inspect relevant
  integration, map objects, mutate, read back, and hand off.
- Define clean, well-organized, correct, optimal, and consent-controlled in
  operational GTM terms so they cannot authorize tracking-plan redesign or
  general container cleanup.
- Treat an actual named-container configuration request as in-scope read/write
  authority for required create/update/reuse operations, while retaining strict
  no-delete, no-cleanup, no-publish, and no-external-system boundaries.
- Replace the heavy mandatory configuration contract with a proportional
  internal requirement-to-object map used directly for mutation, saved-state
  comparison, and idempotency.
- Remove `Specification complete`; use `Configured`, `Partial`, `Blocked`, or
  `Deferred`, with `Configured` requiring authoritative workspace readback.
- Prioritize current official documentation for technical validity and schema,
  then lock the installed template version/capabilities before tag or
  transformation design.
- Restrict container inspection to objects relevant to destinations, sources,
  consumers, conflicts, duplicates, consent, templates, folders, and reuse.
- Strengthen clean architecture with default naming, shallow folder grouping,
  active LUT/RLT consideration for real deterministic mappings, direct DLV
  preference, and narrow CJS only for required shape conversions.
- Add fail-closed media ecommerce rules: explicit catalog/feed identifiers,
  no silent item dropping or unapproved coercion, and a separate validity
  condition when empty/undefined transformation output would not stop a tag.
- Deepen operational readback for GA4, Google Ads, Microsoft Advertising,
  Meta, TikTok, Snap, templates, consent, references, fingerprints, conflicts,
  uncertain writes, partial failures, and no-op reruns.
- Keep basic CMP blocking as the default and advanced/native denied-state
  behavior as an explicit, product-specific, officially proven requirement.
- Reduce the default handoff to the configured workspace, exact changes,
  conformance, consent route, blockers/partial state, and external dependencies.

### What Users Should Do

- Provide the target GTM container and approved analytics tracking plan; add an
  explicit media brief when media tags are required.
- Expect the skill to discover container/template/CMP facts first and ask only
  for missing inputs that block actual configuration.
- State advanced consent and first-party-data requirements explicitly; otherwise
  the skill applies strict/basic CMP blocking.
- Use the separate audit/cleanup and Preview recette skills for those tasks, and
  authorize publication independently after configuration review.

### Validation

- Contract tests protect the operational north star, one workflow, four-status
  model, orientation/execution/judgement structure, official-source priority,
  relevant-only inspection, naming/folders, advanced variables, fail-closed
  ecommerce, saved readback, and no-publication boundary.
- Generic configuration scenarios retain all v2.1 capability coverage and add
  exact no-enrichment analytics, Meta invalid-item eligibility, installed-
  template version gating, deterministic LUT/RLT selection, naming/folder
  organization, and unavailable-mutation blocking.
- Comparator, packaging, release, formatting, lint, compile, and deterministic
  archive checks gate the release.

### Known Limits

- Static saved-state verification does not replace browser, network, CMP, or
  vendor-platform runtime recette.
- The skill cannot finish when critical source, destination, consent, template,
  conflict, or mutation access is unavailable; it reports `Blocked` rather than
  completing a specification workflow.
- Vendor event catalogues and field schemas remain live official-source lookups,
  not frozen skill content.
- Publication, site/dataLayer development, general audit/cleanup, server-side
  GTM, CAPI, event-ID architecture, and browser/server deduplication remain
  outside this release.

## 2.1.0

### Why This Release Matters

- Makes approved analytics tracking-plan fidelity explicit: the configuration
  skill implements the collection contract and does not optimize or redesign it.
- Keeps current official documentation essential for validity, discrepancy
  detection, and technical configuration without treating it as authorization
  to substitute events or enrich payloads.
- Makes the skill's best-practice playbooks authoritative for GTM architecture;
  existing container state is integration evidence, not a precedent to copy.

### What Changed

- Add a dedicated tracking-plan fidelity and conformance contract covering
  collection versus implementation semantics, workbook/source scope,
  documentation discrepancies, preflight decisions, and exact equality proof.
- Classify plan/documentation differences as `blocking-error`, `advisory`, or
  `implementation-note`. Preserve valid approved custom events and omitted
  optional fields; block invalid/reserved events and missing required fields
  instead of substituting or inventing values.
- Require approved-to-intended conformance before mutation and
  approved-to-saved conformance before `Configured`, including exact scope,
  event, timing, parameter, source, and literal equality.
- Add a dependency-free normalized JSON comparator that reports missing, extra,
  and mismatched requirements and scope with deterministic exit codes.
- Select the target implementation from the applicable skill playbook and
  current official/template documentation before evaluating local reuse.
- Classify reuse candidates as conformant, conformant with naming debt,
  nonconformant, conflicting, or unknown. Never copy a legacy pattern or add a
  parallel implementation around a known conflict.
- Keep naming conventions as presentation compatibility only when consistent
  and clear; they never determine implementation architecture.
- Add adapter schema/action discovery, complete pagination, page-limit and
  quota handling, plus a current-operation journal that separates pre-existing
  workspace changes, current-run mutations, and final totals.
- Expand handoff and static acceptance to include source scope, discrepancy
  classes, deterministic conformance output, best-practice reuse proof, and
  exact workspace change attribution.

### What Users Should Do

- Supply an approved analytics tracking plan or exact direct analytics decision.
- Review blocking discrepancies before the affected requirement is configured;
  treat advisories as information unless the approved input is explicitly
  amended by the analyst or tracking-plan owner.
- Expect the skill to inspect the container for conflicts and safe reuse without
  reproducing legacy architecture or performing unauthorized cleanup.
- Preserve the normalized conformance reports with the implementation handoff.

### Validation

- Contract tests protect tracking-plan fidelity, discrepancy classification,
  collection/infrastructure separation, best-practice-first architecture,
  constrained reuse, pagination discovery, and workspace change attribution.
- Structured scenarios cover valid custom-event advisories, blocking plan
  errors, omitted optional fields, mixed legacy patterns, conflicting existing
  implementations, and explicit source-scope classification.
- Comparator tests prove order-independent equality and detection of event
  substitutions, unauthorized parameters, scope differences, missing/extra
  requirements, and invalid normalized input.
- Formatting, lint, unit tests, Python compilation, release checks,
  deterministic package contents, and whitespace checks gate the release.

### Known Limits

- The comparator validates normalized JSON equality; it does not interpret
  arbitrary client workbooks or decide analytics semantics.
- The skill reports analytics-plan optimization opportunities but leaves plan
  creation and revision to the tracking-plan analyst or tracking-plan skill.
- Existing container conflicts can block an affected requirement when updating
  or disabling the conflicting object is outside the authorized scope.
- Runtime recette, publication, server-side GTM, CAPI, event-ID architecture,
  and browser/server deduplication remain outside this release.

## 2.0.0

### Why This Release Matters

- Gives the skill one clear north star: translate approved client-side analytics
  and media requirements into the smallest authorized, statically verifiable,
  traceable, and consent-controlled GTM change set.
- Makes configuration completion possible from an approved tracking plan,
  direct human requirement, or media brief without requiring runtime access.
- Retains deliberate complexity where it protects compound consent, shared tag
  architecture, data shape, workspace safety, and mutation integrity.

### What Changed

- Add a mandatory adapter-neutral configuration contract with evidence grades,
  requirement records, field mappings, an object change manifest, external
  dependencies, statuses, and static completion invariants.
- Replace the runtime-dependent completion status with `Configured`,
  `Specification complete`, `Partial`, `Blocked`, and `Deferred`; runtime
  observations are not a configuration input or completion condition.
- Define `Configured` by authoritative current-workspace state, including an
  idempotent no-op when the target already matches; do not mislabel that as a
  new live change.
- Model GTM trigger semantics explicitly: firing-trigger OR, filter-row AND,
  exception precedence, regex intent, Data Layer Variable versions, firing
  options, priority, schedule, live-only behavior, pause state, and sequencing.
- Generalize strict/basic consent from one vendor block to the smallest reusable
  block set that represents category/purpose, vendor, product, and initialization
  requirements without the mutually-exclusive-AND trap.
- Add static handling for GA4 custom definitions, key events, Google tag/property
  surfaces, media-platform administration, outside-container installations, GTM
  Zones, template restrictions, and other external dependencies.
- Date the vendor-consent capability baseline and require fresh official evidence
  for every implementation.
- Make MCP/API/UI mutation manifest-driven and deterministic, with workspace
  synchronization, conflict inspection, stable IDs/fingerprints, pre-change
  state, saved-object readback, partial-state recovery, and idempotency checks.
- Replace prose-only semantic fixtures with structured configuration scenarios
  that validate the packaged decision contract without claiming model or runtime
  test coverage.
- Adopt Semantic Versioning at `2.0.0`; this major version reflects incompatible
  changes to configuration statuses, evidence, validation, and handoff contracts.
  Earlier date-based tags remain historical releases.
- Align repository/package metadata. The pre-existing `v2026.7.20` tag pointed
  to metadata that still declared `2026.7.18`; release checks now verify that a
  release tag points at the tested clean commit.

### What Users Should Do

- Supply an approved tracking-plan requirement or direct analytics requirement
  for analytics work, and a human media brief for media work.
- Supply or approve the source event contract, representative payloads, consent
  policy, destination identifiers, and mutation scope; runtime access is not a
  prerequisite.
- Review the configuration contract and object manifest before mutation, then
  review the exact saved-object and external-dependency handoff.
- Use the separate GTM Preview recette skill when observed browser behavior is
  required, and authorize publication independently.

### Validation

- Release checks enforce the north star, evidence grades, status model, direct
  routing, object manifest, trigger semantics, compound-consent logic, adapter
  idempotency, external dependencies, metadata, and exact package contents.
- Eleven structured scenarios cover GA4, media, compound consent, shared Google
  conflicts, missing source contracts, no-tool specifications, partial writes,
  idempotent reruns, GA4 administration, an unlisted browser vendor, and the
  deferred server-side/deduplication boundary.
- Formatting, lint, unit tests, Python compilation, deterministic package build,
  clean-tree validation, tag-to-commit validation, and whitespace checks gate
  the release.

### Known Limits

- The skill configures client-side web GTM only and does not publish or create
  container versions.
- It does not create tracking plans, develop the site/dataLayer, make legal
  decisions, or certify runtime browser, network, CMP, or vendor behavior.
- GTM adapter capabilities vary; an unsupported mutation field produces a
  complete specification or explicit blocker rather than an improvised write.
- Server-side GTM, Conversions API, event-ID architecture, and browser/server
  deduplication remain deferred future extensions.

## 2026.7.18

### Why This Release Matters

- Separates analytics tracking-plan intake from media-team implementation briefs.
- Expands the skill from a GA4/Meta foundation into a scalable client-side
  analytics and media configuration system.
- Makes strict/basic consent blocking the default and advanced consent an
  explicit, evidence-backed exception.

### What Changed

- Add dedicated browser playbooks for Google Ads, Microsoft Advertising, Meta,
  TikTok, and Snapchat, plus a mandatory official-documentation fallback for
  every other media platform.
- Require field-level media mappings from business action through dataLayer,
  GTM variable, installed template field, and official destination parameter.
- Add Google basic/advanced Consent Mode architecture and vendor-native consent
  routing without conflating built-in checks with strict firing prevention.
- Expand advanced consent beyond GA4 with a per-product capability map covering
  the Google tag family, Microsoft Advertising UET, Microsoft Clarity,
  Matomo/Piwik PRO adaptive analytics, TikTok native cookie control, and strict
  fallbacks for products without proven denied-state behavior.
- Prefer one reusable CMP blocking trigger per vendor/platform and block
  unknown, uninitialized, and denied states by default.
- Require a valid once-per-page base/config initialization path after both an
  initial consent grant and a later grant; a blocked page-load trigger is not
  treated as if it retries automatically.
- Require blocking-trigger event scope to cover every consumer event, protect
  sequenced tags at the initiating tag, and distinguish revocation from
  unloading a script that already ran.
- Require direct native filtering of the CMP's documented vendor-state variable
  and prohibit speculative consent CJS, JavaScript, table, or Boolean helpers.
- Treat a CMP value outside its documented contract as a blocking integration
  defect rather than a runtime transformation requirement.
- Require every new GTM object to serve a current requirement or documented
  platform/template constraint, including base tags and manual page views.
- Reuse semantically equivalent Google product blocks; split them only when
  vendor identity, event scope, consent policy, ownership, or route differs.
- Reconcile destination-level consent choices with shared Google tag/linker
  execution units so incompatible basic and advanced routes are not claimed.
- Clarify that cross-vendor consent research does not add unsupported analytics
  tag-configuration routes.
- Keep configuration/base tags from sending page views by default while
  documenting vendor-specific inherent page-load exceptions.
- Add first-party user-data governance for enhanced conversions and advanced
  matching, with explicit approval, source, consent, normalization, and hashing
  requirements.
- Add data-contract, ecommerce-array, Custom JavaScript, Custom Event-first
  trigger, SPA, template-governance, and MCP/API/UI adapter references.
- Expand acceptance scenarios and release checks to protect the new contracts.
- Cross-check release versions and current-section notes, lint in CI, and prove
  exact deterministic runtime-archive contents.
- Include the MIT license in the distributable skill archive.

### What Users Should Do

- Provide a tracking plan or direct requirement for analytics work.
- Provide the media platform, requested business action, destination use, and
  available account/pixel/conversion details for media work.
- Expect the agent to reopen current official vendor and CMP documentation for
  every implementation.
- State explicitly when advanced consent or first-party user-data collection is
  approved; otherwise the skill uses strict/basic vendor blocking.
- Review the object and field-level change map before any separate publication.

### Validation

- Skill structure and direct reference routing are checked automatically.
- Critical analytics/media intake, consent, page-view, official-source,
  template, array, and deferred-scope contracts have regression checks.
- Forward tests cover a GA4/Didomi pre-CMP page view with event-scoped fields,
  mixed GA4 basic and Google Ads advanced consent on a shared Google tag,
  multi-item Meta/TikTok media mapping, an unlisted media vendor, and
  partial-failure handling in a dedicated workspace.
- Unit tests, Python compilation, deterministic package build, and whitespace
  checks are run before release.

### Known Limits

- The skill configures client-side web GTM only.
- Vendor event catalogues and parameter schemas are intentionally not frozen in
  the package; current official documentation is required at execution time.
- Server-side GTM, Conversions API, event-ID architecture, and browser/server
  deduplication remain deferred.
- Full GTM Preview, network, CMP journey, and vendor-diagnostics recette remains
  a separate workflow.

## 2026.7.13

### Why This Release Matters

- Establishes the first repository release for the GTM configuration skill.
- Makes the utility contract explicit for expert web analysts using AI agents.

### What Changed

- Structure the skill into orientation, execution, and judgement layers.
- Add explicit audience, objective, use cases, flexible-input, output, workspace,
  authority, and boundary contracts.
- Add dedicated-workspace preference and approved Default Workspace fallback.
- Keep server-side GTM and deduplication as deferred future capabilities rather
  than permanent exclusions.
- Add repository README, release metadata, release checks, package building,
  CI, contribution guidance, and security guidance.

### What Users Should Do

- Load "SKILL.md" as the runtime entrypoint.
- Provide a tracking-plan row or direct human requirement.
- Allow the agent to discover missing container, template, CMP, and runtime
  evidence when the selected route needs it.
- Review the object-level change map before publication.

### Validation

- Skill frontmatter validator passed.
- Orientation, execution, and judgement structure check passed.
- Required references, direct routes, and repository metadata check passed.
- Runtime package build and unit checks are run before the release is published.

### Known Limits

- V1 configures client-side GTM only.
- Server-side GTM, Conversions API, browser/server deduplication, and related
  routing are deferred to a later version of this same skill.
- Full interactive GTM Preview recette remains a separate workflow.
