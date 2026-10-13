# Conversion Linker and cross-domain architecture

## Contents

- [Purpose](#purpose)
- [Establish ownership](#establish-ownership)
- [Decide whether a Conversion Linker is required](#decide-whether-a-conversion-linker-is-required)
- [Configure cross-domain behavior](#configure-cross-domain-behavior)
- [Reconcile consent and shared Google tags](#reconcile-consent-and-shared-google-tags)
- [Verify saved configuration](#verify-saved-configuration)

## Purpose

Use this playbook for Google Ads or Floodlight click attribution, linker-cookie behavior, and
cross-domain journeys. Do not add a Conversion Linker by habit.

## Establish ownership

Inspect current Google tags, linked destinations, Google Ads and Floodlight tags, existing
Conversion Linkers, hard-coded Google tags, relevant domains, forms, and property-side settings.
Establish whether the requirement belongs to Google Ads/Floodlight GTM configuration, GA4 Admin,
Google tag settings, website code, or a combination.

Current Google guidance normally places GA4 cross-domain domain configuration in GA4 Admin. Record
that work as external unless an exact approved GTM override is required. For Google Ads and
Floodlight in GTM, current guidance may use a Conversion Linker with domain linking.

## Decide whether a Conversion Linker is required

Create or reuse one only after proving:

- which conversion products and tags consume it;
- whether current Google tag architecture already supplies the required behavior;
- whether an existing linker has compatible triggers, domains, consent, and settings;
- whether attribution cookies or incoming linker parameters are needed;
- that another plugin/site implementation does not duplicate it.

Use one compatible linker for aligned consumers rather than one per conversion tag. Separate only
when current official behavior, domain scope, consent, or ownership requires it.

Current [Google Conversion Linker guidance](https://support.google.com/tagmanager/answer/7549390)
says a container that loads a Google tag on every page does not also need a separate linker tag,
and Ads/Floodlight tags initiate a Google tag before sending events. Inspect actual landing-page
coverage and any custom cross-domain/cookie requirements before adding or retiring a linker.
This browser guidance does not remove a documented server Conversion Linker requirement.

## Configure cross-domain behavior

From the current official documentation and visible template fields, resolve:

- auto-link domains and exact matching implications;
- incoming linker-parameter acceptance;
- form decoration when required;
- query versus fragment placement;
- trigger scope and initialization order;
- the relationship with `_gl`, click identifiers, and current Google cookie behavior.

Google's current guide limits form decoration to Query Parameter placement, not Fragment. Do not
select both form decoration and fragment placement as if they jointly cover a form journey.

Require an approved domain list. Do not discover domains from arbitrary outbound links or use a
broad parent-domain substring without checking matching behavior. Keep payment providers and other
third parties outside the list unless they participate in the approved measurement journey and
support the required return path.

## Reconcile consent and shared Google tags

Apply the selected basic or explicitly approved advanced Google consent architecture to the linker
and every connected consumer. A basic-blocked Google tag or conversion family must not be
undermined by an unblocked shared linker or configuration path. Conversely, do not attach an
additional block that defeats an explicitly approved advanced route.

Treat GA4, Google Ads, and Floodlight as distinct destinations even when one Google tag loads them.
If their domain or consent requirements are incompatible and current official separation is not
available, block the conflicting configuration rather than hiding it in shared settings.

## Verify saved configuration

Read back the linker tag, triggers, domains, incoming/decorate settings, URL position, consent,
connected Google tags, destinations, and consumers. Confirm no duplicate linker or property-side
cross-domain path was silently added. Record GA4 Admin, site-code, payment-provider, and runtime
journey validation as external dependencies; never claim browser decoration from static GTM
readback.
