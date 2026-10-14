# Triggers and variables

[Native resources](native-resources.md) owns non-Custom-Event triggers, built-ins and LUT/RLT;
[mapping](../data/mapping.md) owns source conversion;
[web consent](../consent/web.md) owns eligibility; [consent lifecycle](../consent/lifecycle.md) owns
initial/later opportunities and pre-readiness events. This guide owns web execution declarations.

## Prefer dataLayer Custom Events

Use the exact approved source event/timing. New source contracts default to one vendor-neutral
Custom Event per business action with a reliable success signal. Reuse a normal trigger across
products when timing, semantics and reference architecture match.

An alternate click/form/URL/history/visibility/timer signal requires analyst approval, evidence that
it represents the action, stable configuration and recorded site dependency/fragility. The chosen
signal proves the approved success semantics.

Match exact event names; regex represents a documented equivalent event family. Business filters
separate actual scenarios sharing a name. Consent remains with its selected eligibility owner.
Record repeated-event semantics and name ordinary Custom Event triggers `CE - <event_name>`.

## Model trigger Boolean logic

Firing triggers are OR alternatives; rows within a trigger are AND; any matching exception blocks.
Groups, sequencing and firing options have separate lifecycle behavior. Record the complete
expression and use the smallest representable graph. Test intentional regex anchoring/escaping
against positive and negative examples. [Web consent](../consent/web.md#build-a-safe-vendor-block)
owns denial-predicate composition.

## Select variables by purpose

Use DLV for direct event data, Constant for reusable stable identity, settings variables for compatible
shared fields, LUT/RLT for actual deterministic scenarios, narrow CJS for required shape conversion,
and URL/auto-event variables for approved alternate sources. [Mapping](../data/mapping.md) owns
method selection and [organization](../organization.md) owns reuse and naming.

DLV Version 1 uses literal-dot keys and replaces object state; Version 2 uses nested paths and can
merge object state. Select against the actual source contract. A version change requires analysis
of every referencing tag, trigger, table and transformation because resolution/persistence changes.

## Inspect advanced tag execution settings

Every active in-scope created/updated/unpaused/reused/untouched tag declares its lifecycle role,
normal-trigger semantic keys and actual native types/roles, block keys, consent topology,
Additional/built-in checks, firing option and pre-CMP policy. Declared sets equal native
`firingTriggerId`/`blockingTriggerId`. A fully authored paused creation still declares its intended
topology. Pause/remove actions instead preserve exact pre-change trigger/consent state and disposition.

Page View, DOM Ready, Window Loaded, Initialization and Consent Initialization are page-load
lifecycle types. Later virtual-page Custom Event/History Change represents event-driven navigation.
Inspect priority, schedule, live-only setting, pause and setup/cleanup references. Consent owners
supply the corresponding opportunity and eligibility for each role.

Represent pre-CMP behavior explicitly: source after readiness, later fresh event, approved
`drop-unconsented-occurrence`, proved replay, or external dependency. The approved requirement must
accept any selected loss of coverage. [Lifecycle](../consent/lifecycle.md) owns recovery semantics.

Use once-per-event normally; select once-per-page/unlimited only for the approved lifecycle.
Priority determines asynchronous start order. A completion dependency needs sequencing support.

## Use tag sequencing only when required

Prefer independent tags when their template handles initialization. A strict documented dependency
requires setup/cleanup sequencing and explicit setup-failure behavior. The initiating tag's complete
predicate protects the sequence because sequenced tags bypass their own firing/blocking triggers.

The current execution model represents tags with ordinary firing triggers. Setup/cleanup-only tags
fall outside that capability, so requirements needing that topology remain `Blocked` and outside
this release's field-test acceptance. A supported independent native route can satisfy the requirement
when its semantics match. Inspect existing sequences for impact even when their mutation is blocked.

## Official entry points

- https://support.google.com/tagmanager/answer/7679316
- https://support.google.com/tagmanager/answer/7679219
- https://support.google.com/tagmanager/answer/7679318
- https://support.google.com/tagmanager/answer/6238868
- https://support.google.com/tagmanager/answer/2772421
- https://developers.google.com/tag-platform/tag-manager/datalayer
- https://support.google.com/tagmanager/answer/7683362
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags
