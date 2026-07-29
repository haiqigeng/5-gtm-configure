# Configure GTM

An agent-neutral operational skill for expert web analysts using Codex, Claude, or another capable
AI agent to configure clean, well-organized, technically correct, best-practice, and
consent-controlled client-side Google Tag Manager workspaces.

## Current Release

**v5.1.0** strengthens client-side first-party-data configuration without changing the skill's
utility-first north star. It requires an explicit collection mode and authorized consumer scope,
selects the narrowest correct Google tag or variable owner, separates `user_id`, user-provided
data, user properties, and advertising matching, and improves release-tooling reliability.

## Who It Serves

- Expert web analysts, analytics consultants, and GTM specialists.
- Analysts implementing approved analytics tracking plans.
- Media specialists requesting browser tags through an explicit implementation brief.
- AI agents with a GTM MCP, API, authorized export/import path, or signed-in UI.

## Utility Objective

Operationally implement an approved analytics tracking plan and, when requested, an explicit media
implementation brief inside a client-side GTM workspace. Create, update, or reuse every required
applicable client-side web-container object: tags, normal and blocking triggers, user-defined and
built-in variables, templates, folders, Google tag configuration/destinations, workspace controls,
and explicitly authorized Zones, environments, or container settings. Use current official
documentation and installed-template capabilities; preserve approved analytics semantics exactly;
support platform-specific media and consent requirements; verify every saved change; and never
publish.

The unit of success is the saved, verified GTM object graph—not a plan, recommendation, or
specification. Governance and static proof protect configuration quality but do not replace actual
configuration.

Use these meanings:

- **Clean:** no avoidable duplicate, known unresolved conflict, redundant helper, or speculative
  future object within the requested setup; no authority for general cleanup.
- **Well organized:** clear default or approved naming, shallow folders where useful, understandable
  references, and semantic reuse.
- **Correct:** faithful inputs, current official technical validity, compatible source and template
  fields, correct trigger/consent logic, and saved-state readback; not runtime certification.
- **Optimal:** the smallest maintainable best-practice GTM architecture within the approved
  requirements; never tracking-plan optimization.
- **Consent controlled:** strict/basic CMP blocking by default and advanced/native behavior only
  when explicitly requested and proven for the exact product.

## Current Client-Side Use Cases

- Configure Google tag identities/destinations and GA4 events, native ecommerce, user lifecycle
  fields, and Enhanced Measurement collision decisions from an approved tracking plan or exact
  direct analytics decision.
- Configure a documented non-GA4 browser analytics destination, including Matomo, Piwik PRO, Adobe,
  or another supported destination, from an approved analytics contract.
- Configure Google Ads, Floodlight, Microsoft Advertising, Meta, TikTok, Snap, LinkedIn, Pinterest,
  X, Reddit, Criteo, affiliate networks, and another officially documented browser media product
  from a human brief.
- Create or update tags, normal and blocking triggers, DLVs, constants, settings variables, LUTs,
  RLTs, narrow transformations, folders, templates, built-in variables, Google tag configuration,
  destinations, and advanced tag settings.
- Inspect applicable Zones, environments, and container settings, and change them only with explicit
  high-impact authority.
- Implement strict/basic CMP gating by default, including Google consent default/update ownership,
  and explicitly requested Google, Microsoft, or vendor-native advanced/cookieless/anonymous
  behavior.
- Implement current OneTrust, Cookiebot, Didomi, conditional TCF 2.3/Additional Consent, or another
  documented CMP state/lifecycle pattern without borrowing signal semantics from a different CMP
  or making legal-purpose decisions.
- Configure explicitly requested first-party user-data features with controlled sources and consent.
- Handle ecommerce arrays, catalog/feed identifiers, and source-to-destination shape conversion
  without speculative eligibility helpers; runtime missing data remains a site/dataLayer and
  recette dependency.
- Reconcile multi-destination, brand, region, hostname, and environment routing with a safe no-match
  path that never defaults unknown traffic to production.
- Reuse compatible objects and reconcile relevant duplicate/conflict risks without auditing or
  cleaning unrelated container content.
- Apply explicit delta changes—including update, rename, trigger/destination fanout, pause, and
  unpause—after tracing every affected consumer and preserving pre-change state.

## Inputs

The skill discovers safe information before asking. Applicable inputs are:

- Target GTM account and web container; a dedicated workspace name is optional.
- Approved tracking-plan scope or exact direct analytics event/fields/source/timing.
- Explicit media brief: platform, business action, destination use, and identity.
- Exact dataLayer event and required paths; representative payloads only when a transformation or
  ambiguous shape requires them.
- Installed or named CMP and its documented grant state; basic blocking is the default.
- Explicit advanced-consent or first-party-data request with the required policy/source details.
- Conditional conversion labels, catalog/feed conventions, matching fields, or environment mapping.

An actual request to configure a named container implies read access and create/update/reuse
authority for its in-scope GTM objects in a dedicated workspace. It does not authorize deletion,
general cleanup, another container, publication, or changes outside GTM.

## Outputs

A successful run returns:

- a dedicated workspace containing the complete saved configuration;
- created, updated, reused, and intentionally untouched in-scope GTM objects;
- exact analytics approved-to-saved conformance or media brief/official-schema mapping;
- saved source variables, native/supported-template fields, direct payload mappings, normal
  triggers, consent route, firing settings, naming, and folders;
- installed-template version and relevant permissions/defaults;
- an official-source manifest plus approved-input and implementation-decision provenance;
- authoritative object readback, resolved references, fingerprints, workspace conflict state, and
  deterministic object-graph diff and idempotent rerun result;
- a compact recette-ready manifest with expected execution, payload mappings, consent states, saved
  object IDs/references, partial state, blockers, and external dependencies;
- confirmation that runtime recette and publication did not occur.

Use `Configured`, `Partial`, `Blocked`, or `Deferred`. If mutation access or a critical decision is
missing, use `Blocked`; do not convert the run into a successful specification workflow.

## Workflow Architecture

The runtime package remains organized around three layers:

1. **Orientation** defines the north star, operational quality, requirement authority, minimal
   intake, boundaries, and official-source priority.
2. **Execution** uses one internal configuration loop, then loads detailed analytics, media,
   consent, data, trigger, template, naming, and adapter playbooks only when required.
3. **Judgement** assigns an operational status from authoritative saved state and returns a concise
   handoff without claiming runtime behavior.

`SKILL.md` directly routes every reference. The workflow is deliberately short; sophistication
lives in conditional configuration requirements and implementation traps.

## Key Defaults And Traps

- Preserve every approved analytics event, outgoing field, literal, source, filter, and success
  moment. Report documented alternatives without silently changing them.
- Validate GA4 event/field names, reserved names, current collection limits, required types, and PII
  exposure against live official sources; block an invalid affected requirement without silently
  truncating, coercing, removing, or enriching it.
- Use an explicit media brief for media business intent and current official browser documentation
  for each platform's schema.
- Inspect the installed template version before designing its fields or transformations. Use a
  native or supported template first; unavailable install/update authority blocks instead of
  silently authorizing Custom HTML.
- Select best-practice architecture before container reuse. Existing prevalence is not authority.
- Inspect only relevant objects for destinations, consumers, conflicts, duplicates, CMP signals,
  folders, and reuse.
- Use direct DLVs first, named constants for stable reusable values, settings variables for genuinely
  shared fields, LUT/RLT for real deterministic mappings, and CJS only for required shape changes.
- Follow the default naming convention and group several related objects in a shallow folder. Keep a
  coherent existing convention only as presentation.
- Keep base/config tags from sending page views by default and reconcile all known automatic/manual,
  Enhanced Measurement, Event Builder, SPA, plugin, partner, and hard-coded paths.
- Preserve every required ecommerce item. Do not assume analytics IDs match media catalogs, silently
  drop invalid items, coerce unapproved types, or invent content/value/currency fields.
- Treat a transform returning empty/undefined as runtime data quality, not as a firing gate. Map the
  approved fields directly and add a payload condition only when the explicit brief or current
  browser documentation requires it.
- Default to strict/basic CMP blocks that cover every consumer event and block unknown,
  uninitialized, and denied states. Independent grants require OR-denial across reusable blocks.
- Use advanced consent or first-party data only after explicit request and current product/template
  proof.
- Create/reuse a dedicated workspace, preserve pre-existing changes, mutate dependencies first,
  re-read every save, and make the identical rerun a no-op.
- Distinguish `GT-`, `G-`, and `AW-` identities, Google tags from connected destinations, and
  inherited settings/consumers before changing Google routing.
- Prefer native GA4 ecommerce and explicitly govern Enhanced Measurement overlap, `user_id`
  lifecycle, user properties/content groups, `traffic_type`, and `debug_mode`.
- Batch unresolved critical inputs after safe discovery, validate the versioned configuration
  contract before mutation, and compare intended versus saved object graphs deterministically.
- Never publish or create a GTM version.

## Official Documentation Policy

Reopen current official vendor, GTM, CMP, and installed-template sources for every implementation.
The skill stores durable decision procedures and traps, not permanent event catalogues.

For analytics, the approved tracking plan controls business semantics; current official
documentation validates technical appropriateness and feasibility. A valid recommended alternative
is advisory. An invalid/reserved/missing-required/incompatible requirement blocks the affected tag.

For media, the brief controls business intent and current official platform documentation controls
the destination schema. Never infer one vendor from another.

## Workspace And Mutation Policy

Prefer a GTM MCP, then API, then an authorized complete export/import path, and use the UI for
unavailable semantic operations. Discover exact adapter actions, pagination, limits, return shapes,
and conflict behavior before writing.

Resolve the dedicated workspace by stable ID, capture pre-existing changes and fingerprints, build
the full object graph, write in dependency order, and read each object back. On an uncertain write,
read before retrying. On partial failure, stop dependent writes and preserve the exact saved recovery
boundary. Do not publish to expose a mutation.

## Boundaries

The skill performs client-side GTM configuration only. It does not create or optimize tracking
plans, develop a site/dataLayer, run a general container audit or cleanup, execute Preview/browser/
network/CMP recette, make legal decisions, complete external platform administration, publish, or
create GTM versions.

Server-side GTM, Conversions API, browser/server deduplication, and event-ID architecture remain
future extensions. An explicitly supplied browser `event_id` can be mapped only when current
browser documentation and the installed template support it; this does not authorize generation or
server design. Consent-capability entries for unsupported analytics products do not add new
analytics tag-configuration routes.

## Repository Map

- `SKILL.md`: operational entrypoint and direct routing.
- `agents/openai.yaml`: OpenAI interface metadata.
- `references/01-orientation/`: north star, intake, authority, boundaries, and official sources.
- `references/02-execution/`: operational workflow and detailed configuration playbooks.
- `references/03-judgement/`: saved-state acceptance and concise handoff.
- `scripts/validate_configuration_contract.py`: strict v4 authority and provenance validation.
- `scripts/validate_contract_conformance.py`: deterministic analytics contract comparator.
- `scripts/diff_object_graph.py`: normalized intended-versus-saved object-graph comparison.
- `scripts/check_release.py`: dependency-free structure/content/release checks.
- `scripts/build_skill_package.py`: deterministic runtime archive.
- `tests/`: code and configuration-trap regression checks.

## Related Skills

- GA4 tracking-plan skill: create or review the measurement plan.
- GTM container audit/cleanup skill: audit hygiene and perform approved cleanup.
- GTM Preview recette skill: execute interactive runtime validation.

## Install The Skill

Copy `SKILL.md`, `agents/`, `references/`, the three runtime scripts in `scripts/`, and `LICENSE` into
the target agent's skill directory. Repository tests and release tooling are not runtime files.

## Release Checks

Run:

~~~powershell
python -m pip install -e ".[dev]"
python -m ruff format --no-cache --check scripts tests
python -m ruff check --no-cache scripts tests
python scripts/check_release.py --tag v5.1.0 --release-notes CHANGELOG.md
python -m unittest discover -s tests -v
python -m compileall -q scripts
python scripts/build_skill_package.py --output dist/configure-gtm-v5.1.0.zip
git diff --check
~~~

Releases use Semantic Versioning: `vMAJOR.MINOR.PATCH`. Increment MAJOR for incompatible skill or
output-contract changes, MINOR for backward-compatible capability additions, and PATCH for
backward-compatible fixes.
