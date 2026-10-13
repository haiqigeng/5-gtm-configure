# Server Google Ads

## Route

Use native Google server tags and the current official procedure. Prove the Google Analytics Client,
server Conversion Linker, conversion ID/label, event trigger, and any value/currency/transaction
mapping. Google documents automatic reading of transaction ID, conversion value, and currency from
corresponding ecommerce fields; inspect the current tag before adding overrides.

Enhanced conversions are optional, not a prerequisite for ordinary server conversion tracking.
Only when enhanced conversions are explicitly in scope, map approved `user_data` through the documented web event route and
server Event Data. Record normalization/hash ownership and external Google Ads activation. Prefer
the narrowest documented consumer and timing: an event override for conversion-page data, a
User-Provided Data Event route for approved earlier-page capture, or tag-wide collection only when
the current Google tag setup explicitly authorizes that wider lifecycle. Enumerate every effective
consumer; never widen user data merely because one destination can consume it.

For earlier-page capture, configure the native UPD variable on the actual capture-event sender
when its value first becomes available. The documented event-level `user_data` override can carry
it through a GA4 Event tag to the distinct server User-provided Data Event consumer. A Google tag
that ran only at CMP initialization cannot establish this later source's availability. See the
current [UPD server route](https://developers.google.com/tag-platform/tag-manager/server-side/ads-user-data)
and [Google event-override guidance](https://support.google.com/google-ads/answer/13262500).

Treat conversion tracking and remarketing as separate native server tag routes. For remarketing,
prove the current Google Ads Remarketing tag, conversion ID, GA4 Client/Event Data input, trigger,
and browser-tag migration disposition. Do not silently reuse conversion parameters as remarketing
parameters or retain an identical browser remarketing tag without an explicit overlap decision.

Google server migration guidance owns duplication: do not add a generic CAPI event ID. Reconcile or
remove an equivalent browser conversion tag only with explicit disposition authority. Consent Mode
is configured web-side and processed by consent-aware Google server tags.

Official source: https://developers.google.com/tag-platform/tag-manager/server-side/ads-setup

Official remarketing source:
https://developers.google.com/tag-platform/tag-manager/server-side/ads-remarketing-setup

Fail closed if Conversion Linker, conversion identity, GA4 Client, or exact native tag fields cannot
be proved. When enhanced conversions are in scope, their activation and complete user-data route
are additional required proofs.
