# Triggers and variables

## Contents

- Approved event and Boolean logic
- Variable semantics and execution settings
- Sequencing boundaries

For non-Custom-Event triggers, built-in variable selection, LUT/RLT mapping or environment routing,
read [native-triggers-and-variables.md](native-triggers-and-variables.md). The
[CMP reference](cmp-consent.md) owns blocking predicates, initial/late page-view timing, SPA consent
opportunities and events before CMP readiness. Do not repeat those rules inside each trigger.

## Prefer dataLayer Custom Events

Use the exact approved dataLayer event and timing. When an approved input authorizes a new source
contract, default to one exact vendor-neutral Custom Event per business action whenever the dataLayer
can provide the success signal. Reuse the same normal trigger across analytics and media tags only
when event timing and semantics are identical and the selected reference architectures remain
compatible.

Create a different trigger type only when:

- no reliable business event exists;
- the analyst approves the fallback;
- an approved site contract, supplied implementation artifact, or authoritative human decision establishes that the chosen signal represents the action;
- the selector, URL, history state, visibility rule, or timing is stable;
- the configuration result records the resulting fragility and external site dependency.

Do not create click, form, timer, scroll, visibility, DOM, or URL triggers merely because GTM supports them. A click is not automatically a successful form submission, purchase, or lead.

## Configure Custom Event triggers precisely

- Match the exact dataLayer event name by default.
- Use a regex event name only for a real, documented family of equivalent events.
- Keep consent out of the normal business trigger when a shared vendor block can express it cleanly.
- Add business filters only when the same event name legitimately represents distinct scenarios.
- Check whether the event can repeat and whether one tag execution per push is correct.

Name normal triggers `CE - <event_name>`.

## Model trigger Boolean logic

Record the complete Boolean expression before creating triggers:

- firing triggers on one tag are alternatives: any matching firing trigger can make the tag eligible;
- filter rows within one trigger are cumulative and must all match;
- any matching blocking/exception trigger prevents the tag from firing;
- trigger groups, setup/cleanup sequencing, and tag firing options add separate lifecycle rules;
- regex event names and filters must be deliberately anchored or unanchored, escaped, and tested against supplied positive and negative examples.

Use the smallest trigger graph that expresses the approved logic. Do not compress independent OR-denial conditions into one trigger whose AND filters can never match together.

## Select variables by purpose

| Need | Preferred variable |
| --- | --- |
| Direct event value | DLV |
| Stable ID or semantic constant | Constant |
| Shared Google configuration/event fields | Google tag settings variable when it genuinely simplifies the design |
| Exact multi-scenario mapping | Lookup table |
| Pattern-based deterministic mapping | Regex lookup table |
| Required array/object or multi-step conversion | Narrow Custom JavaScript |
| Stable URL component | Built-in or user-defined URL variable when no dataLayer source is available |
| Stable click/element property | Auto-event variable only for an approved non-dataLayer fallback |

Prefer dataLayer values over DOM extraction. Do not use a JavaScript Variable to access a value already exposed cleanly through a DLV.

For every DLV, record whether Version 1 literal-dot or Version 2 nested-path semantics match the
actual source key. Version 1 treats dots in the configured name literally and does not recursively
merge object values across pushes; Version 2 interprets dot notation as nested keys and can merge
dataLayer object state. Choose
from the approved source contract, not preference. A change between versions can change nested
resolution, persistence, object merging, and every consumer, so never update a reused DLV version
without tracing all tags, triggers, tables, and transformations that reference it.

## Inspect advanced tag execution settings

For every created, updated, unpaused, reused, or untouched active tag in scope, record its execution
topology: lifecycle role (baseline/page-load or event-driven), every semantic normal-trigger object
key with its verified GTM trigger type and role, blocking-trigger object keys, Additional Consent
Checks, template-owned built-in checks, firing option, and any pre-CMP policy. The normal and block
sets must equal the tag target's `firingTriggerId` and `blockingTriggerId` arrays. A Click, Form,
Element Visibility, Scroll Depth, YouTube, History Change, Timer, JavaScript Error, or Trigger Group
must retain its real type; never relabel it as a Custom Event to satisfy the artifact.

Do not assign a target execution topology to a removed or paused tag. Preserve its exact
`pre_change` trigger/consent state and authorized disposition instead.

Classify Page View, DOM Ready, Window Loaded, Initialization, and Consent Initialization as
page-load lifecycle triggers, never as event-driven source triggers. Under strict/basic consent,
an automatic Google-tag page-view owner must therefore use baseline/page-load topology with the
verified CMP readiness/grant trigger plus its vendor block. Keep an approved virtual-page Custom
Event or History Change route event-driven when it represents a later SPA navigation.
Inspect priority, custom schedule, live-only behavior, pause state, setup/cleanup references, and
all other advanced settings while doing so.

Under strict/basic consent, an event-driven tag uses its approved source trigger plus the vendor block; a
baseline/page-load tag uses a verified CMP readiness/grant event plus the vendor block. Additional
Consent Checks stay unset when that block owns eligibility. Under explicitly approved advanced
consent, do not attach a defeating block or Additional Consent Check.

For an event that may occur before CMP readiness, record one explicit policy: prove the source only
occurs after readiness, wait for a later fresh event, intentionally drop the unconsented occurrence,
perform one proved replay, or hold the change on an external dependency. A blocking trigger does not
queue or replay an event. `drop-unconsented-occurrence` is valid only when the approved requirement
accepts that loss; never silently substitute it for measurement coverage.

Record the selected firing option, normally once per event unless the approved lifecycle requires once per page or unlimited execution. A higher priority changes asynchronous start order but does not create a completion dependency; use sequencing when a documented dependency must finish first.

## Use tag sequencing only when required

Prefer independent tags triggered by the same business event when the vendor template handles initialization correctly. Use setup/cleanup sequencing only when current official documentation or installed template behavior requires a strict dependency.

GTM setup and cleanup tags invoked through sequencing ignore their own firing and blocking triggers. Put the applicable vendor block on the initiating tag, verify that a denied/unknown event never starts the sequence, and do not treat an exception attached only to the sequenced tag as protection.

Document failure behavior: decide whether the event tag should run if the setup tag fails. Do not use sequencing to hide a missing base-tag or consent design.

Current execution-model boundary: a setup/cleanup-only tag with no ordinary firing trigger is not
representable by this release's execution topology. Do not add a dummy trigger, ineffective child
exception, or a manually edited checkpoint to make it pass. If the installed template supports a
correct independent native route, use that route; otherwise mark the sequencing-dependent
requirement `Blocked`. Do not claim setup/cleanup-only coverage or include it in this release's
field-test acceptance. Inspect existing sequences for impact even when their mutation is blocked.

## Official entry points

- https://support.google.com/tagmanager/answer/7679316
- https://support.google.com/tagmanager/answer/7679219
- https://support.google.com/tagmanager/answer/7679318
- https://support.google.com/tagmanager/answer/6238868
- https://support.google.com/tagmanager/answer/2772421
- https://developers.google.com/tag-platform/tag-manager/datalayer
- https://support.google.com/tagmanager/answer/7683362
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags
