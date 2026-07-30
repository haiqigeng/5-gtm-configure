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
client-approved category/vendor/purpose policy. These patterns reduce repeated discovery but never
replace current official CMP documentation or legal decisions.

## Common state contract

For every CMP, establish from current documentation and container evidence:

- earliest initialization/default point;
- documented readiness and change events;
- exact category, vendor, purpose, or product state variable;
- unknown/uninitialized/undefined representation;
- initial grant, denial, later grant, repeated readiness/change, and revocation;
- page-to-page and SPA lifetime;
- template fields, permissions, defaults, and Google consent mapping when used.

For strict/basic gating, use the documented state variable directly and make every non-granted
state block. Independent required grants use OR-denial across the smallest reusable set of blocks.
Do not create a generic consent Custom JavaScript helper.

## OneTrust

Open the current OneTrust GTM and Google Consent Mode documentation. Inspect the deployed OneTrust
script/template version and the site's actual category IDs. Confirm current documented dataLayer
events and state variables rather than copying example category values from another client.

Official entry points:

- https://my.onetrust.com/articles/en_US/Knowledge/UUID-301b21c8-a73a-05e8-175a-36c9036728dc
- https://my.onetrust.com/articles/en_US/Knowledge/UUID-d81787f6-685c-2262-36c3-5f1f3369e2a7

Reconcile auto-blocking, site-deployed scripts, the CMP template, GTM additional-consent checks, and
manual blocking. Do not create parallel default/update paths. Treat region mappings and category
ownership as approved CMP inputs.

## Didomi

Inspect the current Didomi web SDK, direct-site versus GTM deployment, documented readiness/change
events, vendor/purpose variables, and exact vendor identifiers. Prefer documented Didomi state
variables and events; do not parse a consent string with custom code when a direct variable exists.

Official entry points:

- https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/events-and-variables
- https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/tag-managers/google-tag-manager/configure-the-didomi-gtm-integration

Prove that a vendor grant includes every required purpose when the client's policy requires both.
Keep readiness and change triggers repeatable only where the consumer must become eligible after a
later grant.

## Axeptio

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
under strict/basic behavior, prevent the service tag before its grant; use advanced Google behavior
only when explicitly requested, and do not add Additional Consent Checks or exceptions that create
an unproved double gate.

For page-load tags, select the documented Axeptio readiness/grant opportunity that supports initial
and later consent without duplicate initialization. For business-event tags, retain the business
trigger and apply the reusable service block across its full event scope. Read back the CMP tag,
template fields, consent defaults/updates owner, event and state variables, service predicates, and
every consumer.

## Secondary CMPs

For Cookiebot, Commanders Act/TrustCommander, Usercentrics, or Quantcast, use the common state
contract and reopen the selected CMP's current official GTM and consent documentation. Confirm its
installed template, deployment owner, initialization and update lifecycle, exact grant state,
Google consent mapping, and revocation behavior. These products remain supported but do not borrow
the dedicated implementation details of OneTrust, Didomi, or Axeptio.

## Other CMPs

For another identifiable CMP, follow the same state contract. Locate current official GTM and
consent documentation, inspect the installed template, and record exact events and variables. If
current primary evidence cannot establish a critical grant or lifecycle rule, block the affected
tag rather than borrowing a OneTrust, Didomi, or Axeptio pattern.

## Saved-state acceptance

Complete the consent truth table in the handoff reference. Read back every CMP tag, default/update
setting, normal trigger, exception/additional-consent check, predicate, event scope, firing option,
and consumer. Confirm that unknown and denial fail closed for basic routes, explicit advanced routes
remain unblocked as designed, repeated events cannot duplicate initialization, and revocation does
not receive an unsupported static guarantee.
