# Official source policy

## Contents

- [Principle](#principle)
- [Authority by decision](#authority-by-decision)
- [Research procedure](#research-procedure)
- [Run record](#run-record)
- [Official entry points](#official-entry-points)
- [Conflict and failure](#conflict-and-failure)

## Principle

Use current primary documentation at execution time. Never rely on memory, analogy, an old tag, or
an informal label for a vendor event, field, type, template capability, consent behavior, CMP
signal, or identity. Unofficial sources are discovery aids, never sole authority for a write.

The approved analytics decision controls collection semantics; current documentation validates
technical feasibility. Never use documentation as permission to substitute or enrich a valid
contract. The media brief controls business intent; current official browser documentation controls the vendor
schema. The inspected installed template/version controls what GTM can actually store.

Do not copy an event catalogue into the skill. Reopen the exact live product, feature, CMP, and
template sources because schemas and capabilities change.

## Authority by decision

| Decision | Primary evidence |
| --- | --- |
| Analytics meaning, fields, source, timing | Approved tracking plan or exact direct decision |
| Analytics validity, limits, and documented appropriateness | Current official analytics/GTM/template documentation |
| Media objective and identity | Explicit current media brief |
| Media destination event and fields | Current official platform browser documentation |
| Source values and shape | Approved dataLayer/source mapping; sample only when shape matters |
| GTM mechanics | Current GTM/API documentation plus inspected native/installed template |
| Client consent policy | Explicit approved client input |
| Product/CMP consent capability | Current official product and CMP documentation plus target-container evidence |
| Existing integration and reuse | Target workspace; never best-practice authority |

## Research procedure

For every applicable product and CMP:

1. Open the official page for the exact client-side web feature and access it during the run.
2. Confirm product, surface, current template/version, permissions, defaults, and automatic behavior.
3. Extract only the event/field requirement, type, shape, enum, cardinality, conditional rule, and
   consent behavior needed for the approved implementation.
4. For analytics, compare official findings with the approved event, fields, sources, literals,
   filters, and timing. Classify a difference as `blocking-error`, `advisory`, or
   `implementation-note`; never modify the approved contract silently.
5. For media, map the approved objective and source values to the exact official browser event and
   installed-template fields. Never borrow another vendor's schema.
6. For consent, establish the exact signal lifecycle and whether denied state blocks, holds,
   suppresses storage, or sends a documented limited request. Record the configured route without
   making a legal decision.
7. Retain URL, title, access date, affected requirement/object, and the supported decision in the
   run manifest.

## Run record

Keep four labels distinct: source dataLayer/configuration key, GTM variable, template UI field, and
vendor request parameter. Record provenance only where it governs a write: official source, exact
product/template, approved locator, type/shape, consent route, discrepancy, and unresolved conflict.
Do not create a citation ledger for self-evident names.

## Official entry points

Start from these primary indexes, then open the exact feature page. Dedicated playbooks contain
their product-specific entry points.

| Area | Primary index |
| --- | --- |
| GTM help and object behavior | https://support.google.com/tagmanager/ |
| GTM API object surface and Parameter schemas | https://developers.google.com/tag-platform/tag-manager/api/reference/rest |
| GTM dataLayer | https://developers.google.com/tag-platform/tag-manager/datalayer |
| Google tag and GA4 | https://developers.google.com/tag-platform/ and https://developers.google.com/analytics/ |
| Google Consent Mode | https://developers.google.com/tag-platform/security/concepts/consent-mode |
| Google Ads and Floodlight | https://support.google.com/google-ads/ and https://support.google.com/campaignmanager/ |
| Microsoft Advertising UET and Microsoft Clarity Consent Mode | https://learn.microsoft.com/en-us/advertising/ and https://learn.microsoft.com/en-us/clarity/ |
| Meta Pixel | https://developers.facebook.com/docs/meta-pixel/ |
| TikTok Pixel standard events and GTM | https://ads.tiktok.com/help/ |
| Snap Pixel and GTM | https://developers.snap.com/marketing-api/Ads-API/snap-pixel |
| LinkedIn, Pinterest, X, Reddit, Criteo | Use the official product help/developer domains linked by their media playbooks. |
| Matomo and Piwik PRO tracking code through GTM | https://developer.matomo.org/ and https://help.piwik.pro/ |
| TCF 2.3 and Additional Consent | https://iabeurope.eu/transparency-consent-framework/ and the current Google integration page |
| OneTrust, Didomi, Axeptio | Use the dedicated official links in `cmp-platform-patterns.md`. |

For an unlisted supported browser vendor, CMP, or template, locate and cite its current official
documentation. Lack of a dedicated playbook never permits inference.

## Conflict and failure

When sources disagree, first confirm product, surface, version, and date. Preserve a technically
valid approved analytics choice and report a recommended alternative as advisory. Stop an invalid,
reserved, missing-required, incompatible, or unsupported analytics requirement until its owner
amends it. For media mechanics, prefer the directly applicable current official page over local
precedent. If critical official evidence is unavailable or still contradictory after checking
another official page, mark the affected object `Blocked`; do not fill the gap from memory.
