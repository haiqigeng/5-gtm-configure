# CMP and consent gating

## Contents

- Basic gate and observation
- CMP evidence and complete blocking predicate
- Static expectations

For a named CMP load [cmp-platform-patterns.md](cmp-platform-patterns.md); for actual TCF deployments
load [tcf-consent.md](tcf-consent.md). Advanced/native consent requires explicit approval and the
exact product capability in [vendor-consent-modes.md](vendor-consent-modes.md); Google routes also
use [google-consent-mode.md](google-consent-mode.md). Existing configuration alone is not approval.
If the current execution unit conflicts with the requested/default policy, resolve that before
adding a consumer. Reuse applicable explicit approval without asking again.

Read [cmp-lifecycle.md](cmp-lifecycle.md) when initial or late-grant timing, pre-CMP business events,
withdrawal, SPA initialization or pipeline transport is affected. A gate never replays an earlier
event. Pre-CMP policy must be explicit; do not assume accepted loss or use a Trigger Group as a queue.

## Default to strict/basic gating

Unless the analyst explicitly requests and approves advanced/native consent behavior, prevent every analytics and media vendor tag from loading or firing before the required consent is granted.

Use the smallest reusable set of CMP blocking/exception triggers that expresses the complete approved predicate. One vendor/platform block is preferred when one native state represents the grant; use additional shared category/purpose, product-consent, or initialization blocks when those are independent required grants. Apply the complete set to the vendor's base/configuration and event tags in scope. Make unknown, undefined, uninitialized, and denied state block.

Keep firing opportunity and consent eligibility separate. A verified CMP readiness/grant event may
be the normal trigger that lets a base/configuration or page-view tag run on initial or later grant;
it does not replace the reusable vendor block. Attaching both is intentional defense in depth and
keeps the tag protected if its normal-trigger lifecycle later changes.

Use a normal Custom Event trigger for the business action and a separate vendor block, for example:

- `CE - purchase`
- `Block - Didomi - Meta denied`

Do not repeat consent conditions inside every business trigger when a shared vendor block expresses the approved policy safely.

Before changing a tag, inspect all normal-trigger filters, exception predicates, Additional Consent
Checks, built-in behavior, and setup/cleanup callers. Remove only equivalent custom eligibility
conditions from in-scope firing triggers when the shared block takes ownership. Retain business,
host, environment, and genuinely independent consent predicates. Never edit a shared trigger for
unrelated consumers without authority. A CMP lifecycle event is a firing opportunity, not a duplicate
custom consent condition to remove.

The static validator detects structurally complementary firing/block predicates only when the
exception's event constraints are also covered. It does not prove arbitrary regex equivalence,
variable aliases, or CMP value semantics. Review actual event coverage and supplied denied/unknown
values before removing a condition; a narrower exception is not evidence that the firing condition
is redundant.

Under this strict/basic topology, leave Additional Consent Checks unset rather than adding a second
copy of the same consent predicate. Template-owned built-in consent checks remain visible and are
recorded separately; do not claim that they were removed. For explicitly approved advanced/native
behavior, use the documented consent defaults/updates and built-in behavior without a defeating
block or Additional Consent Check.

Design the normal-trigger lifecycle separately from the block. A page-load trigger that is blocked while consent is unknown or denied does not retry automatically. When a base/configuration tag must initialize after consent, use verified CMP readiness/grant events and an appropriate once-per-page control so both an initial grant and a later grant have a valid firing opportunity. Keep any page-view event and late-consent page-view policy separate from initialization.

## Existing consent conventions

The vendor-block pattern above is the preferred convention for new strict/basic implementations.
For an existing, inspected container convention, the same `strict-basic` mode also accepts:

- `web_enforcement.mechanism: firing-trigger-condition`, with `evidence` identifying the inspected
  CMP state contract and an exact native GTM `grant_condition`. Every firing trigger must contain
  that condition in its `filter`. Supported conditions are positive `equals` or `contains`, with
  exactly `arg0` (the consent variable) and `arg1` (the granted value/token). No negation, empty
  value or unknown/denied match is accepted. Establish exact token boundaries and unknown values
  from the deployed CMP; substring matching is not proof of vendor membership. Complex regex or
  multiple independent grant conditions remain outside this alternate convention.
- `web_enforcement.mechanism: additional-consent-checks`, with `evidence` and `default_bindings`
  mapping each configured consent type to `{object_key, field_path}`. Each native path must resolve
  to `denied` in the inspected default-owner tag, which fires on Consent Initialization. Bind that
  owner as an explicit dependency; include a consent-kind requirement for it. Review the actual
  template/version to establish that each field controls the declared consent type and that updates
  occur before business events. This route accepts event-driven, once-per-event tags only; it does
  not solve page-load or once-per-page retry behavior.

Both conventions require unknown state `deny`, no parallel vendor blocks, exact tag settings and
current official/CMP evidence. The validator checks saved structure; actual CMP behavior remains a
recette responsibility. See [Google's consent checks](https://support.google.com/tagmanager/answer/10718549)
(checked 2026-09-29). An ungated approved client policy is a separate
[contract route](configuration-contract.md#map-consent-and-deduplication), never an invented CMP.

## Distinguish observation from gating

Classify the final GTM logic:

| Mechanism | Counts as a gate only when |
| --- | --- |
| Built-in consent requirement | It prevents the tag from firing under the selected model, rather than only changing tag behavior. |
| Firing-trigger condition | It evaluates false for every denied and unknown firing path. |
| Blocking/exception trigger | It evaluates true for every denied and unknown firing path and wins over the normal trigger. |
| Consent-aware/native advanced behavior | It intentionally allows documented limited or cookieless execution under denied state; describe it as advanced consent behavior, not strict blocking. |
| Observation only | It reads, displays, logs, or transmits consent state without preventing firing. This is not a gate. |

Never report a tag as strictly gated merely because its template lists built-in checks or a consent variable resolves in Preview.

## Research the installed CMP

Before creating a condition:

1. Open the current official CMP documentation for the installed product/version and GTM integration.
2. Identify separately the CMP initialization/readiness events, consent-change events, state variables/cookies/APIs, vendor identifiers, and value format.
3. Obtain the approved site/CMP signal contract and representative values before initialization, after denial, and after grant.
4. Establish event frequency, ordering, state lifetime, and returning-choice behavior from that contract.
5. Confirm the exact category/purpose and vendor identities used by this site.
6. Prove from GTM filter semantics that undefined state is expected to remain blocked. Treat a supplied value outside the CMP's documented format as an integration defect and block the affected design until the source contract is corrected or authoritatively clarified.

Do not infer that similarly named CMP events and variables have the same role. For Didomi, for example, establish readiness/change events independently from enabled-vendor state. Use the exact category/purpose and vendor identities documented and supplied for the site. Do not append a delimiter by convention; when the CMP serializes a delimited list, match the exact token format established by official documentation and the approved representative value.

## Build a safe vendor block

Define the exception's event scope before its consent-state condition. A shared block must be able to activate on every GTM event used by each consumer tag; a condition that reads the right CMP value is ineffective on an event the trigger does not match. In a Custom Event-first design, default a vendor-wide block to a verified `.*` Custom Event regex rather than repeating the current event-name inventory or using a CMP-only event name. Use a narrower matcher only when the block intentionally serves a documented consumer subset, and record that reason. If a consumer uses an event type the shared block cannot cover, stop and redesign the exception scope before claiming strict gating.

Inspect tag sequencing separately. GTM tags invoked as setup or cleanup tags ignore their own firing and blocking triggers. Do not rely on the sequenced tag's exception: make the initiating tag's complete predicate prevent the sequence under unknown or denied consent, and prove the expected static path from the configured references.

Use the documented CMP state variable directly in the blocking trigger whenever a native GTM filter can express the policy safely. For a vendor-enabled list, the default pattern is one negative condition:

    {{DLV - <CMP enabled vendors>}} does not contain <exact documented vendor token>

Derive the DLV key, operator, category/purpose and vendor token, delimiter, case, and value type from current CMP documentation and approved representative values. For a CMP that exposes a documented Boolean or keyed state, test that source directly. Avoid substring collisions by matching the exact documented token format.

GTM combines multiple filter rows inside one trigger with logical AND, while any matching blocking trigger prevents its consumer tag. Do not add mutually exclusive denial rows to one trigger. Use one documented native condition whose negative result covers every non-granted state when one signal represents the complete grant. When independent required grants each need OR-denial behavior, use separate reusable blocks or another officially supported native representation. Do not create a Custom JavaScript, JavaScript, lookup-table, or Boolean consent helper when documented CMP variables can be tested directly.

If the official CMP contract cannot be represented safely with a native GTM condition, mark the affected consent design `Blocked` and request an authoritative CMP signal or approved architecture. Do not invent a parser or helper variable to compensate for an undocumented source shape.

Test the block against similar vendor IDs and another-vendor-only consent. Do not combine different platforms in one block. If one platform is represented by multiple verified CMP identities, document their exact Boolean logic inside that platform's block.

## Validate the final decision

For each vendor tag, derive the expected static result:

| Contract state | Strict/basic configured expectation |
| --- | --- |
| CMP not initialized or value undefined | Expected not to fire. |
| Required category/purpose or vendor denied | Expected not to fire. |
| Different vendor granted only | Expected not to fire. |
| Complete required grant and normal trigger occur | Eligible under the selected firing option. |
| Consent revoked | Later GTM invocations are expected to remain blocked; already-loaded behavior follows the documented configured limitation. |
| Consent granted after initial denial | The configured late-consent/page-view path matches the approved policy without a known duplicate. |

For a base/configuration tag, also prove statically that an initial grant and a later grant each have a valid configured initialization opportunity without repeated initialization.

For explicitly approved advanced behavior, replace the strict non-fire expectation with the exact officially documented limited-data configuration expectation and label it clearly. Do not present it as an observed request.
