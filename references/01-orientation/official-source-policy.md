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
an informal label for a vendor event, field, type, template capability, Client claim,
Transformation, consent behavior, CMP signal, dedup identifier, or identity. Unofficial sources
are discovery aids, never sole authority for a write.

Approved analytics decisions control collection semantics; current documentation validates
technical feasibility. A media brief controls business intent; current official product
documentation controls the browser and server destination schemas. The inspected installed
template/version controls what GTM can actually store and send. An official API does not prove that
an official or compatible GTM server template exists.

Do not freeze event or parameter catalogues in this skill. Reopen the exact live product, feature,
CMP, Client, Transformation, and template sources for each implementation.

## Authority by decision

| Decision | Primary evidence |
| --- | --- |
| Analytics meaning, fields, source, timing | Approved tracking plan or exact direct decision |
| Analytics validity, limits, and documented appropriateness | Current official analytics/GTM/template documentation |
| Media objective and destination identity | Explicit current media brief |
| Browser/server media event and fields | Current official platform documentation for the exact product |
| Source, wire, and Event Data shape | Approved source mapping plus current sender protocol and claiming Client documentation |
| GTM mechanics | Current GTM/API documentation plus inspected native or installed template |
| Client consent policy | Explicit approved client input |
| Product/CMP consent capability | Current official product/CMP documentation and target-container evidence |
| Existing integration and reuse | Complete target workspace evidence; never architecture authority |

## Research procedure

For every applicable product and CMP:

1. Open the official page for the exact web, server, or pipeline feature during the run.
2. Confirm product, surface, current template/version, publisher, permissions, network hosts,
   defaults, automatic mapping, secret fields, response behavior, and dedup ownership.
3. For server ingress, prove the request class, intended claiming Client, claim criteria/priority,
   and generated Event Data. Do not infer Event Data from the web dataLayer.
4. Extract only the event/field requirement, type, shape, enum, cardinality, conditional rule,
   consent behavior, and identifier needed for the approved implementation.
5. For analytics, classify differences as `blocking-error`, `advisory`, or
   `implementation-note`; never silently modify valid approved semantics.
6. For media, map the approved objective independently to the exact browser and/or server product;
   never borrow another vendor's schema or assume that similarly named fields are equivalent.
7. For consent, establish signal lifecycle, transport behavior, event coverage, and the one
   effective destination enforcement mechanism without making a legal decision.
8. Retain URL, title, access date, affected requirement/object, and the supported decision.

## Run record

Keep source dataLayer/configuration key, web variable, wire field, claiming Client/Event Data path,
server owner, template UI field, and vendor request parameter distinct. Record provenance where it
governs a write: exact product/template, approved locator, type/shape, consent, dedup, discrepancy,
and unresolved conflict. Never persist credentials or raw PII in the evidence record.

## Official entry points

Start from these primary indexes, then open the exact feature page. Destination playbooks contain
more specific links.

| Area | Primary index |
| --- | --- |
| GTM help and web objects | https://support.google.com/tagmanager/ |
| GTM API object surface | https://developers.google.com/tag-platform/tag-manager/api/reference/rest |
| Server-side GTM overview | https://developers.google.com/tag-platform/tag-manager/server-side |
| Send data to server GTM | https://developers.google.com/tag-platform/tag-manager/server-side/send-data |
| Server Clients API | https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.clients |
| Server Transformations API | https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.transformations |
| Common server Event Data | https://developers.google.com/tag-platform/tag-manager/server-side/common-event-data |
| Server Consent Mode | https://developers.google.com/tag-platform/tag-manager/server-side/consent-mode |
| Google tag and GA4 | https://developers.google.com/tag-platform/ and https://developers.google.com/analytics/ |
| Google Ads and Floodlight server setup | https://developers.google.com/tag-platform/tag-manager/server-side/ads-setup and https://developers.google.com/tag-platform/tag-manager/server-side/fl-setup |
| Microsoft Advertising | https://learn.microsoft.com/en-us/advertising/ |
| Meta | https://developers.facebook.com/docs/marketing-api/conversions-api/ |
| TikTok | https://ads.tiktok.com/help/ |
| Snap | https://developers.snap.com/marketing-api/Conversions-API/Introduction |
| LinkedIn | https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/conversions-api |
| Pinterest | https://developers.pinterest.com/docs/track-conversions/track-conversions-in-the-api/ |
| X | https://docs.x.com/x-ads-api/measurement/web-conversions |
| Reddit | https://ads-api.reddit.com/docs/v3/guides/programs/capi |
| Criteo | https://developers.criteo.com/ |
| OneTrust, Didomi, Axeptio | Use the exact official links in `cmp-platform-patterns.md`. |

For an unlisted product, CMP, or template, locate and cite its current official documentation.
Lack of a dedicated playbook never permits inference.

## Conflict and failure

When sources disagree, confirm product, surface, version, and date. Preserve a technically valid
approved analytics choice and report alternatives as advisory. Stop an invalid, reserved,
missing-required, incompatible, or unsupported requirement until its owner amends it. Prefer the
directly applicable current official page over local precedent. If critical evidence remains
unavailable or contradictory, mark only the affected dependency subtree `Blocked`; do not fill the
gap from memory or stop independent safe work.
