# Official source policy

## Contents

- [Principle](#principle)
- [Evidence hierarchy by decision](#evidence-hierarchy-by-decision)
- [Research procedure](#research-procedure)
- [Research record](#research-record)
- [Official entry points](#official-entry-points)
- [Conflict and failure handling](#conflict-and-failure-handling)

## Principle

Use current primary documentation at execution time. Give it priority for technical validity,
destination schemas, GTM behavior, and consent capability. Never rely on memory, analogy, an old
implementation, or an informal media event label for a vendor event, parameter, type, array shape,
accepted value, template field, consent capability, CMP event, CMP variable, or vendor identity.

Use an approved analytics tracking plan or exact direct analytics decision to establish the authorized analytics collection contract. Use current official documentation to validate its classification, requirements, types, shapes, limits, and technical feasibility; never use documentation as permission to substitute or enrich a valid approved analytics contract. For media, use the media brief for the business objective and current official media documentation to establish the destination event and field schema. Use the applicable skill playbook, installed template, approved source contract, and representative payloads to design the static implementation. Use target-container state only for integration constraints, conflicts, consumers, and conformant reuse candidates. Runtime evidence is outside this skill and is not an input requirement.

## Evidence hierarchy by decision

| Decision | Primary authority |
| --- | --- |
| Analytics collection selection and business meaning | Approved tracking plan or exact direct analytics decision |
| Analytics technical validity and documented appropriateness | Current official GA4, Google tag, GTM, and installed-template documentation; report differences without silently changing the approved selection |
| Media business objective | Current media-team brief |
| Media destination event and field schema | Current official platform documentation |
| GTM reference architecture and field implementation | Applicable skill playbook plus current native/installed-template documentation, version, and visible field definitions |
| Source values and timing | Approved dataLayer/source contract and representative payloads |
| Client consent policy | Analyst-provided approved policy |
| Product consent capability and denied-state behavior | Current official product documentation, installed template, approved policy, and target-container configuration |
| CMP signal, event lifecycle, and vendor identity | Current official CMP documentation plus the approved site/CMP signal contract and target-container state |
| Existing local integration, conflicts, consumers, and reuse evidence | Target container and workspace; never a best-practice authority |

Treat unofficial articles and community examples as discovery aids only. Do not use them as the sole support for a required value or behavior. Do not let an existing tag override current official documentation.

## Research procedure

For each platform, product, and CMP involved:

1. Open the current official page that directly covers the selected browser implementation.
2. Confirm that the page applies to client-side web and the installed product/template version.
3. Extract the official event name, standard/custom/deprecated status, fields, requirement status, types, formats, enumerations, cardinality, and conditional rules.
4. For an approved analytics contract, compare those findings with the exact approved event, fields, sources, literals, types, and timing. Classify each difference as `blocking-error`, `advisory`, or `implementation-note`; do not modify the approved contract.
5. For consent work, establish whether denied state blocks, holds, suppresses cookies, or transmits a documented limited payload; record storage, identifiers, data use, modeling, defaults, updates, and revocation.
6. Inspect the installed GTM template and map documentation concepts to its visible fields.
7. Establish source values, timing, state lifetime, and CMP signals from approved inputs and any
   representative payload required by the mapping.
8. Retain critical provenance from the configuration map and create one concise per-run source
   manifest containing source URL, page title, access date, exact client-side product/template,
   affected requirement or object, discrepancy class, decision, and unresolved contradiction.

Do not copy an event catalogue into the skill and treat it as permanent. Re-open the live catalogue
for every implementation because vendors change standard events, parameters, requirements,
templates, and consent features. The skill may retain stable GTM mechanics and decision rules
(trigger Boolean logic, DLV version implications, template preference, workspace readback), but the
run must still verify any mechanic whose current UI/API or product behavior is material. Keep
volatile vendor schemas, Gallery inventories, template field catalogues, and CMP vendor/purpose
catalogues live rather than static.

## Research record

Record only the technical facts needed to configure and verify each tag:

- official URL, page title, and access date;
- browser/client-side product and installed template/version;
- official event name and classification;
- approved analytics event/field selection and whether the official finding is conformant, advisory, or blocking;
- exact field names and required, recommended, optional, or conditional status;
- accepted type, format, enum, and cardinality;
- source dataLayer key or configuration value;
- source provenance and representative non-sensitive input when mapping or transformation risk
  requires it;
- GTM variable and template field;
- transformation and representative resolved output when a real shape conversion is applicable;
- consent support, per-product classification, denied-state request/storage behavior, selected mode, and CMP mechanism;
- unresolved contradiction or unavailable evidence.

Keep these four layers distinct even when their labels look similar:

1. source dataLayer key;
2. GTM variable;
3. template UI field;
4. vendor request/payload parameter.

## Official entry points

Use these as search entry points, then follow the current page for the exact requested feature:

| Need | Official entry point |
| --- | --- |
| GTM tags, triggers, variables, workspaces, and consent | https://support.google.com/tagmanager/ |
| GTM dataLayer | https://developers.google.com/tag-platform/tag-manager/datalayer |
| GTM Data Layer Variable versions | https://support.google.com/tagmanager/answer/7683362 |
| GTM firing triggers, exceptions, and sequencing | https://support.google.com/tagmanager/answer/7679318 and https://support.google.com/tagmanager/answer/6238868 |
| GTM priority, schedule, live-only behavior, and tag firing options | https://support.google.com/tagmanager/answer/2772421 and https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags |
| GTM API workspaces, synchronization, fingerprints, and mutations | https://developers.google.com/tag-platform/tag-manager/api/v2 and https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces/sync |
| Complete GTM API object surface, built-ins, Google tag configs, destinations, templates, Zones, and environments | https://developers.google.com/tag-platform/tag-manager/api/reference/rest |
| GTM Zones and Environments | https://support.google.com/tagmanager/answer/7647043 and https://support.google.com/tagmanager/answer/6311518 |
| GTM container export/import | https://support.google.com/tagmanager/answer/6106997 |
| GTM Community Template Gallery | https://support.google.com/tagmanager/answer/9454109 |
| GTM template Gallery and template API | https://developers.google.com/tag-platform/tag-manager/templates/gallery and https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.templates |
| GA4 events and ecommerce | https://developers.google.com/analytics/devguides/collection/ga4/reference/events and https://developers.google.com/analytics/devguides/collection/ga4/ecommerce |
| GA4 configuration fields and page views | https://developers.google.com/analytics/devguides/collection/ga4/reference/config and https://developers.google.com/analytics/devguides/collection/ga4/views |
| GA4 user-provided data and User-ID | https://support.google.com/analytics/answer/14077171, https://support.google.com/analytics/answer/14179229, https://support.google.com/analytics/answer/14171268, and https://support.google.com/analytics/answer/9213390 |
| GA4 custom dimensions and metrics | https://support.google.com/analytics/answer/14240153 |
| GA4 collection limits, reserved names, and PII safety | https://support.google.com/analytics/answer/9267744, https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference, and https://support.google.com/analytics/answer/6366371 |
| Google tag settings variables | https://support.google.com/tagmanager/answer/13438166 and https://support.google.com/tagmanager/answer/13438771 |
| Google tag and destination identity | https://support.google.com/tagmanager/answer/12324388, https://support.google.com/tagmanager/answer/12324787, and https://support.google.com/tagmanager/answer/12326985 |
| Google Consent Mode | https://developers.google.com/tag-platform/security/concepts/consent-mode and https://developers.google.com/tag-platform/security/guides/consent |
| Google Ads conversion and remarketing | https://support.google.com/google-ads/answer/7521212 and https://support.google.com/tagmanager/answer/6106009 |
| Google Ads dynamic remarketing schema | https://support.google.com/google-ads/answer/7305793 |
| Google Ads enhanced conversions | https://support.google.com/google-ads/answer/13262500 |
| Google/Floodlight cross-domain measurement and Conversion Linker | https://developers.google.com/tag-platform/devguides/cross-domain |
| Floodlight and Campaign Manager 360 | https://support.google.com/campaignmanager/answer/7554821, https://support.google.com/campaignmanager/answer/3183388, and https://support.google.com/campaignmanager/answer/4599566 |
| Microsoft Advertising UET | https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uetv2customevent and https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_parameters_table |
| Microsoft UET Consent Mode and GTM template | https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_consent and https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_dynamicconsentgtm |
| Microsoft Clarity Consent Mode | https://learn.microsoft.com/en-us/clarity/setup-and-installation/consent-mode and https://learn.microsoft.com/en-us/clarity/setup-and-installation/cmp-integration-guide |
| Meta Pixel browser events | https://developers.facebook.com/docs/meta-pixel/reference/ |
| TikTok Pixel standard events, parameters, and GTM | https://ads.tiktok.com/help/article/standard-events-parameters and https://ads.tiktok.com/help/article/how-to-create-tiktok-event-tags-with-google-tag-manager |
| TikTok Pixel cookie-consent behavior | https://ads.tiktok.com/help/article/how-to-use-cookies-with-tiktok-pixel |
| Snap Pixel and GTM | https://developers.snap.com/marketing-api/Ads-API/snap-pixel and https://businesshelp.snapchat.com/articles/en_US/Knowledge/formatting-pixel |
| LinkedIn Insight Tag | https://www.linkedin.com/help/lms/answer/a418880 |
| Pinterest Tag and GTM | https://help.pinterest.com/en/business/article/google-tag-manager-and-pinterest-tag |
| X Pixel and GTM | https://business.x.com/en/help/campaign-measurement-and-analytics/conversion-tracking-for-websites |
| Reddit Pixel | https://business.reddithelp.com/ |
| Criteo OneTag | https://help.criteo.com/ |
| Matomo analytics in GTM | https://matomo.org/faq/new-to-piwik/how-do-i-use-matomo-analytics-within-gtm-google-tag-manager/ |
| Matomo tracking versus cookie consent | https://developer.matomo.org/guides/tracking-consent |
| Piwik PRO tracking code through GTM | https://help.piwik.pro/support/getting-started/google-tag-manager-install-a-tracking-code/ |
| Piwik PRO consent | https://help.piwik.pro/support/privacy/setting-consent-manager/ |
| IAB Europe TCF 2.3 and Google TCF integration | https://iabeurope.eu/transparency-consent-framework/ and https://support.google.com/admanager/answer/9805023 |
| Didomi GTM events, variables, and integration | https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/events-and-variables and https://developers.didomi.io/cmp/web-sdk/third-parties/tags-management/tag-managers/google-tag-manager/configure-the-didomi-gtm-integration |
| OneTrust GTM and Google Consent Mode | https://my.onetrust.com/articles/en_US/Knowledge/UUID-301b21c8-a73a-05e8-175a-36c9036728dc and https://my.onetrust.com/articles/en_US/Knowledge/UUID-d81787f6-685c-2262-36c3-5f1f3369e2a7 |
| Cookiebot GTM and Google Consent Mode | https://support.cookiebot.com/hc/en-us/articles/360003793854-Google-Tag-Manager-deployment and https://support.cookiebot.com/hc/en-us/articles/360016047000-Cookiebot-and-Google-Consent-Mode |

For any unlisted media platform, CMP, template, or supported feature, locate and cite its current official documentation before configuring it. Lack of a dedicated playbook never permits inference.

## Conflict and failure handling

When sources disagree:

1. Confirm that the current official page directly covers the selected browser feature and template version.
2. For analytics, preserve the approved selection when it remains technically valid and record a documented recommended alternative as advisory.
3. Stop the affected analytics object when the approved contract is invalid, reserved, missing a required field, type/shape incompatible, unsupported, or otherwise unsafe; never substitute a different contract automatically.
4. For media destination schemas and implementation mechanics, prefer the directly applicable current official page over local precedent or analogy.
5. Confirm the approved source contract, installed template, and saved container fields.
6. Record the contradiction, class, impact, and exact analyst decision required.
7. Stop the affected object as blocked if no authoritative source resolves a critical decision.

If an official site is temporarily unavailable, retry or use another official page for the same product. Do not replace unavailable critical documentation with memory or an unofficial tutorial.
