# IAB Europe TCF 2.3 route

## Scope

Load this route only when the approved CMP/site architecture uses IAB Europe TCF for the
client-side web container. TCF 2.3 is the current framework route; do not implement a remembered
TCF 2.2 string, event, vendor mapping, or migration pattern.

This skill connects a confirmed CMP signal to saved GTM configuration. It does not decide whether
TCF applies, select legal bases, choose purposes/special features, approve vendors, certify the CMP,
or interpret the policy for the client.

## Establish authority

Before mutation, require and record:

- the exact CMP, installed version/template, and approved TCF configuration owner;
- the current CMP-generated TC string and event/API contract used by the site;
- the required Global Vendor List identity for each destination;
- approved purpose, special-feature, publisher-restriction, and legitimate-interest decisions;
- whether Google Additional Consent is present and the approved Google vendor mapping;
- the applicable page, region, environment, and revocation lifecycle.

Use current IAB Europe, Google, CMP, and destination documentation. If the approved mapping is
missing or contradicts current product requirements, mark only the affected route `Blocked`.

## Configure plumbing, not policy

1. Prefer the CMP's supported GTM template and native exposed events/variables.
2. Preserve one owner for CMP initialization, TC-string state, and change events.
3. Map the already approved vendor/purpose predicate to the smallest native reusable block set.
4. Make unknown, unavailable, malformed, and incomplete required state block under the basic route.
5. Keep the block event scope compatible with every consumer's normal trigger.
6. If Google Consent Mode is also used, map the approved CMP state to Google defaults/updates through
   the supported CMP template; do not infer one system's values from the other.
7. Pass Google Additional Consent only through the documented CMP/Google path when it is actually
   part of the approved implementation.
8. Apply change and revocation behavior to future executions; do not claim GTM can unload a vendor
   script that already ran.

Do not parse a TC string in Custom JavaScript, reconstruct it, store it in a constant, or create
purpose/vendor decisions from a generic cookbook. Do not equate a present TC string with permission
for the destination.

## Readback

Read back the CMP template/version, initialization and update tags, TC/Additional Consent source,
normal triggers, reusable blocks, complete predicates, event scope, consumers, Google consent
mapping, and revocation path. Record the configured expectation for:

- CMP/TC state unavailable;
- required purpose or vendor denied;
- unrelated vendor granted;
- complete approved grant before the event;
- grant after an earlier blocked event;
- repeatable CMP update;
- revocation.

Runtime decoding, network behavior, and vendor-platform acceptance remain recette work.

## Official entry points

- https://iabeurope.eu/transparency-consent-framework/
- https://support.google.com/admanager/answer/9805023
- https://developers.google.com/tag-platform/security/guides/consent
- the selected CMP's current official TCF 2.3 and GTM integration documentation
