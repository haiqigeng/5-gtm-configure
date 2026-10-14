# Official source policy

## Principle

Use current primary documentation for the changed product, surface and feature, together with the
inspected installed template/Client. An official API establishes protocol behavior; GTM capability
requires the corresponding native or installed-template support. Unofficial material can help locate
primary evidence. [Authority](authority.md#requirement-authority) owns business inputs and approval.

Folder-only organization uses approved target authority and inspected native/container capability.
Product or collection changes require applicable current technical evidence.

## Research procedure

1. Open the exact official feature page and verify its publisher/product relationship.
2. Inspect the installed template/version, permissions, hosts, fields, defaults, automatic mapping,
   secrets and response behavior relevant to the change.
3. For server ingress, establish request class, intended Client, claim criteria/priority and generated
   Event Data from sender/Client documentation and native evidence.
4. Extract the required types, shapes, enums, cardinality, conditional behavior, consent and identity
   rules. Map each media destination independently under its own schema.
5. Classify findings: an invalid or unsupported required implementation is `blocking-error`; a valid
   alternative recommendation is `advisory`; mechanical guidance is an `implementation-note`.
6. Record the source and applied decision against the affected requirements and objects.

The reasoning chain is **official guidance → applicable recommendation → installed capability →
implementation → saved proof**. Distinguish mandatory, conditional, recommended and optional fields.
Only an unmet applicable requirement blocks the affected work; optional match-quality improvements
remain advisory. A documented native schema bridge is usable when its exact mapping and installed
fields fit the approved semantics.

Vendor setup examples may include broad imports, automatic collection, publication or account work.
Apply their technical mechanics within the approved timing, consent and scope. A playbook entry
routes research; support is established for the actual product/template used.

## Reuse current evidence

Reuse concise evidence when product, feature, template/version and decision still apply. Reopen the
relevant official section to check currency, focusing on changed, ambiguous or time-sensitive rules.
Preserve the actual access date unless revisited. The validator's 365-day ceiling is an artifact
validity bound, not a promise that guidance stays current for a year. Resolve event/field catalogues
from their official source during the task rather than treating stored examples as a fixed catalogue.

## Run record

For each included product/collection requirement, retain an `official-current` source with HTTPS URL,
page title, actual access date, supported requirement IDs and a concise `decision` describing the
rule applied. Record approved source, container and sample provenance separately where they establish
mapping or implementation facts. Keep source, variable, wire, Client/Event Data, template and vendor
field identities distinct; [mapping](../data/mapping.md) owns that model.

Schema checks enforce credential-free HTTPS, complete traceability and the access-date range.
The agent establishes publisher authenticity, source relevance and installed-version applicability
under [evidence limits](authority.md#evidence-and-validation-limits). The source indexes below aid
discovery; a newly verified official host can be used without changing the skill.
Apply [persistence privacy](execution.md#handle-secrets-without-false-equality) to the record.

Mark evidence strength as `documented`, `template-confirmed`, `statically-verified` or
`runtime-unverified`; completion statuses remain owned by [acceptance](acceptance.md).

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
| OneTrust, Didomi, Axeptio | Use the exact official links in [Cmp patterns](../consent/cmp-patterns.md). |

For an unlisted product, CMP, or template, locate and cite its current official documentation.
Establish the same product, installed-capability and source evidence before implementing it.

## Conflict and failure

Resolve disagreements by product, surface, version and date, using the directly applicable current
primary source. Preserve technically valid approved analytics choices and report alternatives as
advisory. Invalid/reserved names, missing required fields, incompatible shapes and unsupported
capability require an amended approved decision or implementation. Record the exact missing fact
and continue independent supported work through [dependency readiness](execution.md#contain-failures-by-dependency).
