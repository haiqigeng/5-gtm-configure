# CMP and consent gating

This guide owns web consent eligibility. [Lifecycle](lifecycle.md) owns firing opportunities and
late-event behavior; [CMP patterns](cmp-patterns.md) and [TCF](tcf.md) supply signal discovery;
[product capabilities](product-capabilities.md) classifies documented native behavior.
[Google consent](google.md) supplies Google-specific state and product coordination.

## Default to strict/basic gating

Default to strict/basic behavior: each in-scope analytics/media loader and event is eligible only
after the complete approved grant. Explicitly approved native/advanced routes use their exact
product contract. A `product-specific` topology records product mechanism, signal authority and
unknown-state behavior; its native mechanism owns eligibility. Reuse applicable approved policy
and resolve conflicts at the actual shared execution unit before adding consumers.

For new strict/basic implementations, the smallest reusable set of CMP exception triggers owns
the complete eligibility predicate. Apply it to base/configuration and event tags. One block
suffices when one signal represents the complete grant; independent required grants may need
separate shared blocks. Unknown, undefined, uninitialized and denied states remain blocked.

Normal triggers own the business or lifecycle opportunity. For example, `CE - purchase` supplies
the action and `Block - Didomi - Meta denied` supplies consent eligibility. CMP readiness/grant can
supply the base tag's opportunity while the block independently enforces the complete grant.

When adopting that owner, inspect firing filters, exceptions, Additional Consent Checks, built-in
behavior and sequencing callers. Remove equivalent custom consent predicates only from authorized
in-scope consumers; retain business/host/environment conditions and independent required grants.
Structural complement checks prove only covered event constraints and supported native predicates.
Actual CMP semantics, token boundaries, aliases and arbitrary regex require source evidence.

Under this topology, Additional Consent Checks are unset and template-owned built-in checks remain
recorded as native behavior. Approved advanced/native behavior retains its documented defaults,
updates and limited denied-state execution. [Lifecycle](lifecycle.md) establishes initial/later
opportunities separately from either eligibility mechanism.

## Contract representation

Use `business-trigger-plus-vendor-block` for business-event opportunity plus denial block, or
`cmp-lifecycle-plus-vendor-block` for CMP lifecycle opportunity plus denial block. Bind each execution
topology's `consent_topology_ids` to its destination topology. Declared normal/blocking trigger keys,
mechanism and deny predicate agree with the actual tag references. The
[authoring model](../core/authoring.md) and shared schema own the remaining structure.

## Existing consent conventions

Inspected existing strict/basic conventions can use either supported mechanism:

| Mechanism | Required native proof |
| --- | --- |
| `firing-trigger-condition` | `evidence` identifies the CMP contract; exact `grant_condition` occurs in every normal trigger's `filter`. Supported positive `equals`/`contains` has exactly `arg0` (variable) and `arg1` (meaningful grant value/token). Establish token boundaries and denied/unknown values. The represented contract is a single supported grant condition. |
| `additional-consent-checks` | `evidence` and `default_bindings` map each type to `{object_key, field_path}` resolving to `denied` in the inspected Consent Initialization owner. That owner is an explicit dependency with a consent-kind requirement. Inspect template semantics and update timing. This convention represents event-driven once-per-event consumers. |

Each convention has unknown state `deny`, one effective eligibility mechanism, exact native tag
settings and current official/CMP evidence. The validator proves saved structure; field testing
proves deployed behavior. See [Google consent checks](https://support.google.com/tagmanager/answer/10718549)
(checked 2026-09-29). Explicitly scoped `client-policy-ungated` uses its own
[policy declaration](../core/authoring.md#map-consent-and-deduplication).

## Distinguish observation from gating

Classify by effective behavior:

| Mechanism | Evidence required |
| --- | --- |
| Built-in consent requirement | Establish whether it prevents firing or changes an executing tag's behavior. |
| Firing-trigger condition | False on every denied/unknown firing path. |
| Blocking/exception trigger | True on every denied/unknown firing path, covering every normal-trigger event. |
| Advanced/native consent behavior | Exact approved limited denied-state request/storage contract. |
| Observation | State reading/display/transmission; eligibility requires its separately proved mechanism. |

## Research the installed CMP

Establish product/version and official integration, readiness/change events, state APIs/variables,
category/purpose/vendor identities, format, frequency, ordering, lifetime and returning-choice
behavior. Use approved representative uninitialized, denied and granted values. Each event and
state source has its own role; a similarly named value establishes only its documented role.

Derive the exact token format, case and delimiters from that evidence. The native predicate must
handle every supplied non-granted state. An undocumented or incompatible signal holds the affected
consent design until its owner provides an authoritative contract or approved architecture.

## Build a safe vendor block

The exception's event scope covers every consumer event before its state predicate is considered.
For a Custom Event-first vendor-wide block, use a verified `.*` Custom Event regex. A narrower
scope explicitly identifies its consumer subset. Consumer event types outside that coverage require
a representable exception design.

Use the documented CMP state directly through native GTM filters. A vendor-enabled list commonly
uses this denial predicate with the exact documented token:

    {{DLV - <CMP enabled vendors>}} does not contain <exact documented vendor token>

Boolean/keyed CMP state uses its corresponding documented native condition. Match whole vendor
tokens and test similar IDs and another-vendor-only grant. Each platform's block expresses its
verified category/vendor Boolean logic.

GTM ANDs filter rows within a trigger; matching exception triggers combine as OR-denial for the
consumer. One complete-grant signal can use one native negative predicate. Independent grants use
separate reusable blocks or another officially supported native representation. The CMP signal
contract and native predicate jointly establish eligibility; source-shape uncertainty remains with
the CMP integration owner.

Sequenced setup/cleanup tags use their initiating tag's invocation path. Their own firing/blocking
triggers are bypassed by sequencing, so the initiating predicate must enforce the complete grant
for the whole sequence. Apply the current [sequencing capability](../web/execution.md#use-tag-sequencing-only-when-required)
before representing that architecture.

## Validate the final decision

| Contract state | Strict/basic configured expectation |
| --- | --- |
| Uninitialized/undefined state | Blocked. |
| Any required category/purpose/vendor denied | Blocked. |
| Another vendor granted only | Blocked. |
| Complete grant plus normal opportunity | Eligible under the selected firing option. |
| Revocation | Later GTM invocations blocked; loaded behavior follows its documented lifecycle. |
| Later grant | Approved initialization/page-view opportunity with one owner per occurrence. |

Base/configuration tags need valid initial and later-grant opportunities under the selected policy.
Advanced routes use their precise approved limited-data expectations. Record these as static
configuration expectations; observed runtime behavior belongs to field testing.
