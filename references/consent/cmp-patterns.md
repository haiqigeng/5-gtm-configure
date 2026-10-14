# CMP platform patterns

## Contents

- [Purpose](#purpose)
- [Common state contract](#common-state-contract)
- [OneTrust](#onetrust)
- [Didomi](#didomi)
- [Axeptio](#axeptio)
- [Secondary CMPs](#secondary-cmps)
- [Other CMPs](#other-cmps)
- [Saved-state acceptance](#saved-state-acceptance)

## Purpose

Use this reference after identifying the actual CMP product, deployment path, template/version, and
client-approved category/vendor/purpose policy. These discovery patterns are interpreted through current official CMP evidence and client policy.

## Common state contract

For every CMP, establish from current documentation and container evidence:

- earliest initialization/default point;
- documented readiness and change events;
- exact category, vendor, purpose, or product state variable;
- unknown/uninitialized/undefined representation;
- initial grant, denial, later grant, repeated readiness/change, and revocation;
- page-to-page and SPA lifetime;
- template fields, permissions, defaults, and Google consent mapping when used.

Apply [web consent](web.md) for native eligibility composition and [lifecycle](lifecycle.md) for
initial/later opportunities. This guide supplies product-specific signal discovery.

## OneTrust

Open the current OneTrust GTM and Google Consent Mode documentation. Inspect the deployed OneTrust
script/template version and the site's actual category IDs. Confirm current documented dataLayer
events and state variables rather than copying example category values from another client.

Official entry points:

- https://developer.onetrust.com/onetrust/docs/google-tag-manager
- https://developer.onetrust.com/onetrust/docs/using-google-consent-mode

Reconcile auto-blocking, site-deployed scripts, the CMP template, GTM additional-consent checks, and
manual blocking around one default/update owner. Region/category mappings are approved CMP inputs.

## Didomi

Signal card checked 2026-10-04: `didomi-ready` occurs once at page load and can carry unknown state;
`didomi-consent-changed` follows a user change; `didomi-consent` covers initial state and changes.
`didomiVendorsEnabled`, `didomiVendorsDisabled` and `didomiVendorsUnknown` contain comma-separated
vendor IDs with a trailing comma. Enabled vendors incorporate their required purposes. When no
regulation applies, all notice vendors are enabled; vendors with only essential purposes can also
be enabled. Enabled therefore means CMP eligibility, not necessarily explicit user opt-in; interpret
it using the approved regional and collection policy. Match full tokens and verify the actual API ID
and deployed value format; readiness alone is not a grant.
Source: https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/events-and-variables

Inspect the current Didomi web SDK, direct-site versus GTM deployment, documented readiness/change
events, vendor/purpose variables, and exact vendor identifiers. Use the documented direct Didomi state variables and events.

Official entry points:

- https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/events-and-variables
- https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/tag-managers/google-tag-manager/configure-the-didomi-gtm-integration

Prove that a vendor grant includes every required purpose when the client's policy requires both.
Keep readiness and change triggers repeatable only where the consumer must become eligible after a
later grant.

## Axeptio

Signal card checked 2026-09-29: `axeptio_update` accompanies initial/update choices;
`axeptio_activate_<service>` identifies activation and `axeptio_disable_<service>` refusal or
withdrawal. `axeptio_authorized_vendors` is an array of service names from the site's project.
Use the inspected consent-state variable/template and exact service membership; `$$` entries are
internal, not vendor approval. Check the template's Trigger GTM Events setting and dataLayer name.
Source: https://support.axeptio.eu/en/articles/348263-how-axeptio-communicates-with-gtm-events-and-variables

Inspect the current Axeptio CMP Gallery template, direct-site versus GTM deployment, Project ID,
cookie configuration, dataLayer name, GTM-event option, template version, and permissions. When GTM
owns deployment, verify that the supported template owns initialization at Consent Initialization
and prevent a second site or container initialization.

Official entry points:

- https://support.axeptio.eu/en/articles/273991-integrate-axeptio-via-google-tag-manager
- https://support.axeptio.eu/en/articles/348263-how-axeptio-communicates-with-gtm-events-and-variables
- https://support.axeptio.eu/en/articles/721671-google-tag-manager-and-integrated-consent-management
- https://support.axeptio.eu/en/articles/704808-configure-google-consent-mode-v2-gtm-integration

Verify the current documented readiness/update events, authorized-service state such as
`axeptio_authorized_vendors`, and exact service identifiers from the client's widget rather than
copying example values. Prefer the direct documented dataLayer state when one native GTM predicate
expresses the grant. Keep service-level Axeptio gating separate from Google Consent Mode signals:
apply the selected [web eligibility](web.md) and [Google state](google.md) owners to the actual
service and Google execution units.

For page-load tags, select the documented Axeptio readiness/grant opportunity that supports initial
and later consent without duplicate initialization. For business-event tags, retain the business
trigger and apply the reusable service block across its full event scope. Read back the CMP tag,
template fields, consent defaults/updates owner, event and state variables, service predicates, and
every consumer.

## Secondary CMPs

For Cookiebot, Commanders Act/TrustCommander, Usercentrics, or InMobi CMP, use the common state
contract and reopen the selected CMP's current official GTM and consent documentation. Confirm its
installed template, deployment owner, initialization and update lifecycle, exact grant state,
Google consent mapping, and revocation behavior. Their own verified signals supply the common contract.

Official entry points for the identified product:

- [Cookiebot GTM deployment](https://support.cookiebot.com/hc/en-us/articles/360003793854-Google-Tag-Manager-deployment)
- [Usercentrics consent-aware GTM tags](https://support.usercentrics.com/hc/en-us/articles/18375671341596-How-to-Configure-Google-Tag-Manager-Tags-to-be-Consent-Aware)
- [Commanders Act consent state API](https://community.commandersact.com/consent-management/onsite-api/consent.get)
- [InMobi CMP GTM implementation](https://support.inmobi.com/choice/other-resources/google-tag-manager-gtm-implementation)

InMobi CMP is the current product name for former Quantcast Choice. Quantcast's measurement Live
Tag is a separate destination. Exact deployed CMP/version evidence selects the current source and
signal contract, including any documented replacement for an obsolete integration method.

## Other CMPs

For another identifiable CMP, follow the same state contract. Locate current official GTM and
consent documentation, inspect the installed template, and record exact events and variables. If
current primary evidence cannot establish a critical grant or lifecycle rule, block the affected
tag rather than borrowing a OneTrust, Didomi, or Axeptio pattern.

## Saved-state acceptance

Complete the consent truth table in the configuration result. Read back every CMP tag, default/update
setting, normal trigger, exception/additional-consent check, predicate, event scope, firing option,
and consumer. Confirm that unknown and denial fail closed for basic routes, explicit advanced routes
remain unblocked as designed, repeated events cannot duplicate initialization, and revocation does
not receive an unsupported static guarantee.
