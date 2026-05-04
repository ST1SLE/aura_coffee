# Stage 0 Economical Prerequisites Guide

This file explains how to obtain the Stage 0 launch inputs with the lowest
reasonable spend while avoiding decisions that create legal, provider, or
infrastructure debt.

Snapshot date: 2026-05-04. Prices and provider rules can change; refresh the
linked sources before purchasing or signing anything.

This is not legal or accounting advice. The shop owner/accountant must approve
54-FZ, receipts, refund procedure, personal-data obligations, and published
legal text before live customer orders.

## Stage 0 Inputs We Need

From `README.md`, Stage 0 requires:

- Canonical domain or staging subdomain.
- VPS or hosting provider.
- Production contact email for TLS/provider accounts.
- YuKassa test and live shop access.
- SMS.ru account with balance, `api_id`, and spending limits.
- Yandex Maps keys with Geosuggest/Suggest and Geocoder enabled.
- Controlled real phone number for OTP tests.
- Owner/accountant decision for 54-FZ receipts and refund procedure.
- Legal owner for privacy, consent, public offer, refund policy, and 152-FZ
  checks.

## Current Stage 0 State

Current selected values:

- Canonical domain: `aura-coffee-bakery.ru`.
- Staging subdomain: `staging.aura-coffee-bakery.ru`.
- DNS provider: Beget.
- VPS IPv4: `212.8.226.214`.
- VPS OS: Ubuntu 24.04.4 LTS.
- SSH key: `~/.ssh/aura-vps`.
- Current `A` records observed on 2026-05-04:
  - `aura-coffee-bakery.ru -> 5.101.152.161`
  - `staging.aura-coffee-bakery.ru -> 212.8.226.214`
- VPS baseline completed on 2026-05-04:
  - `deploy` user created with SSH key access.
  - Docker Engine and Docker Compose plugin installed.
  - `ufw` enabled for `22`, `80`, and `443`.
  - Required app, media, and backup directories created.

Stage 0 is not complete yet.

Remaining blockers before we can honestly call Stage 0 done:

| Section | Status | What must happen next |
|---------|--------|-----------------------|
| 4. YuKassa | Deferred / keep mocked | YuKassa currently requires owner/business details. Keep `YUKASSA_BACKEND=fake` until the owner is ready; live/test-shop integration will be handled later with owner details and 54-FZ/refund decisions. |
| 5. SMS.ru | Stage 0 configured | Developer account created, rotated `api_id` stored privately, controlled phone selected, and low-limit posture accepted for initial smoke. Later use the private `api_id` as `SMSRU_API_KEY` only in staging env. |
| 6. Yandex Maps | Keys created / code supports split keys | Two keys exist: `JavaScript API и HTTP Геокодер` and `API Геосаджеста`. Aura supports separate Suggest/Geocoder keys with `YANDEX_MAPS_API_KEY` kept only as a fallback. License/storage decision still blocks delivery launch. |
| 7. Controlled test phone | Selected / private | Use the developer's personal phone for initial OTP smoke; keep the actual number out of committed docs/logs. |

Next DNS action:

- Do nothing until a VPS is purchased.
- Done: `staging.aura-coffee-bakery.ru` now points to the VPS public IPv4.
- Use `staging.aura-coffee-bakery.ru` for the first production-like deploy.
- Keep `aura-coffee-bakery.ru` unchanged until staging is proven and we are
  ready for public launch.
- Point `aura-coffee-bakery.ru` at the same VPS only during the controlled
  cutover.

## Recommended Economical Path

Do not buy everything upfront. Buy only what unblocks the next verified stage.

| Item | Economical starting move | Avoid for now |
|------|--------------------------|---------------|
| Domain | One `.ru` domain plus staging subdomain. | Premium domains, many TLDs, paid SSL. |
| VPS | One Russian 2 vCPU / 4 GB VPS for staging and first launch. | Managed Kubernetes, managed DB, multi-server setup. |
| TLS | Let's Encrypt / Certbot. | Paid TLS certificates unless business requires them. |
| YuKassa | Create test shop immediately; postpone live money until test webhooks and receipts are proven. | Live payment acceptance before 54-FZ/receipt decision. |
| SMS.ru | Create account, get `api_id`, set low spend/volume limits, test one phone. | Branded sender and large top-up before OTP smoke works. |
| Yandex Maps | Create key for testing, but resolve data-storage license question before delivery launch. | Saving free Geocoder results to DB without written license confidence. |
| Legal | Assign owner/accountant/lawyer and draft minimal required pages. | Generic legal package purchase before exact business model is known. |

## 1. Domain And DNS

Goal: get a stable public name for TLS, cookies, CORS, and YuKassa webhooks.

Economical recommendation:

- Buy one `.ru` domain.
- Use `staging.DOMAIN` for prelaunch tests instead of buying another domain.
- Use registrar DNS first; move DNS later only if needed.
- Use Let's Encrypt for TLS.
- Avoid paid SSL and extra TLDs until public launch is proven.

Observed current prices:

- REG.RU lists `.ru` at `169 ₽` on its domain pricing pages.
- Webnames advertises `.ru` domain registration from `189 ₽/year`.

Steps:

1. Search for the cafe brand in `.ru`. Done: `aura-coffee-bakery.ru`.
2. Check renewal price, not only first-year promo price.
3. Register under the shop owner's account, not a developer's personal account.
4. Enable two-factor authentication on the registrar account.
5. Create records later:
   - `A DOMAIN -> VPS_IPV4`
   - `A staging.DOMAIN -> VPS_IPV4`
   - optional `CNAME www -> DOMAIN`

Stage 0 gate:

- Domain owner is correct.
- DNS control is available.
- `DOMAIN` and `staging.DOMAIN` are reserved for the launch plan.

Sources:

- REG.RU `.ru` pricing: https://www.reg.ru/company/prices/domain
- REG.RU `.ru` domain info: https://www.reg.ru/domain/new/RU
- Webnames domain pricing: https://www.webnames.ru/

## 2. VPS Or Hosting Provider

Goal: run the current Docker Compose architecture with private PostgreSQL and
Redis, static frontend builds, nginx, workers, media, and backups.

Economical recommendation:

- Start with one Russian VPS.
- Minimum practical first-launch shape:
  - 2 vCPU
  - 4 GB RAM
  - 50 GB disk
  - static IPv4
  - Ubuntu 24.04 LTS
- Upgrade to 4 vCPU / 8 GB only if build/runtime/media pressure proves it is
  needed.
- Keep Postgres and Redis on the same host first; managed database can wait.

Observed current example:

- Selectel advertises a VDS `2 vCPU / 4 GB RAM / 50 GB disk` plan at
  `650 ₽/month`.
- Selectel also advertises `4 vCPU / 8 GB RAM / 80 GB disk` at `1,100 ₽/month`.
- Selectel claims its cloud servers meet 152-FZ up to UZ-1 and lists PCI DSS,
  ISO 27001, SOC 2, and other attestations. This is useful for due diligence,
  but it does not replace the shop owner's own personal-data obligations.

Steps:

1. Compare two or three Russian VPS providers, but do not over-optimize.
2. Require:
   - Russian-region data center.
   - static IPv4.
   - Docker support.
   - snapshot or backup option.
   - firewall controls.
   - clear invoices for business accounting.
3. Pick the 2 vCPU / 4 GB class first.
4. Create non-root deploy user.
5. Allow only `22`, `80`, and `443`.
6. Create directories:
   - `/opt/aura-coffee`
   - `/var/backups/aura-coffee/postgres`
   - `/srv/aura-coffee/media/menu`

Stage 0 gate:

- VPS provider and monthly budget are approved.
- Hosting region and business documents are acceptable to the owner.
- Server can run Docker and expose only nginx publicly.

Sources:

- Selectel VPS/VDS pricing and compliance claims:
  https://selectel.ru/services/cloud/vps-vds/

## 3. Production Contact Email

Goal: avoid production accounts being tied to one developer's personal inbox.

Economical recommendation:

- Use an owner-controlled email account first.
- Later create `admin@DOMAIN` or `tech@DOMAIN` if the domain provider includes
  cheap mail hosting.
- Do not buy corporate mail just for Stage 0 unless the owner already wants it.

Use this email for:

- Domain registrar.
- VPS provider.
- Let's Encrypt notices.
- YuKassa.
- SMS.ru.
- Yandex developer account.

Stage 0 gate:

- Owner controls the mailbox.
- 2FA is enabled.
- Recovery phone/email are owned by the business.

## 4. YuKassa

Goal: obtain test-shop access now and prepare live access without accepting live
money too early.

Current decision:

- YuKassa stays mocked for now.
- Keep `YUKASSA_BACKEND=fake` in local/staging until the coffee shop owner can
  provide business details and approve 54-FZ/refund decisions.
- Do not spend time fighting YuKassa onboarding as the developer account holder.
  We will resume YuKassa integration when owner details are available.

Economical recommendation:

- Create a YuKassa account and test shop immediately.
- Use test-shop credentials for integration until the whole payment/webhook
  path passes.
- Do not accept live payments until 54-FZ receipt path and refund procedure are
  approved.
- Evaluate "Checks from YuKassa" before renting or buying a separate online
  cash register. YuKassa says this option lets YuKassa handle receipt formation
  without the merchant buying/renting online cash register hardware, registering
  it in the tax office, or contracting with an OFD.

Important current facts:

- YuKassa onboarding says test payments can be tested without a contract and
  without company data by creating a test shop.
- Live connection requires registration, contract/company data, document upload,
  signing the YuMoney contract, integration setup, and tests.
- Current YuKassa fee page showed common methods at `2.8% + 1% for the receipt`
  and SBP calculated individually. Verify in the actual merchant account before
  launch.

Steps:

1. Register in YuKassa under the owner/business account.
2. Create a test shop.
3. Record:
   - test `shopId`
   - test secret key
   - dashboard URL
4. Confirm live entity type: individual entrepreneur (`ИП`), legal entity, or
   other accepted owner model.
5. Ask accountant which receipt path is acceptable:
   - Checks from YuKassa
   - external online cash register
   - existing shop cash register integration
6. Confirm refund policy with owner.
7. Do not enter live credentials into Aura until Stage 10 of the roadmap.

Stage 0 gate:

- Test shop exists.
- Owner knows what is needed for live contract.
- 54-FZ receipt decision has an owner and a next action.

Sources:

- YuKassa onboarding:
  https://yookassa.ru/docs/support/payments/onboarding/overview
- YuKassa fee page:
  https://yookassa.ru/fees/
- YuKassa 54-FZ receipt solutions:
  https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics

## 5. SMS.ru

Goal: obtain real OTP capability with a controlled cost ceiling.

Current state:

- Developer SMS.ru account has been created.
- Account balance is `0 ₽` in the current UI.
- The SMS.ru page shows `Ваш api_id` at the bottom of the main page. Treat that
  value as a secret and do not paste it into chat, docs, or Git.
- The `api_id` has been rotated and stored privately by the developer.
- In Aura, that value maps directly to the private environment variable
  `SMSRU_API_KEY`.
- The current SMS worker does not send a custom sender name. It posts only
  `api_id`, recipient phone, message, and `json=1` to SMS.ru.

Economical recommendation:

- Create an SMS.ru account.
- Get `api_id`.
- Start with a small balance and strict daily limit.
- Do not pay for a branded sender until generic service-code delivery is proven
  and the owner decides the branding is worth it.
- Use one controlled phone for first smoke tests.

Important current facts:

- SMS.ru documents `api_id` as the convenient authentication method and exposes
  a `/sms/cost` endpoint to calculate message cost before sending.
- SMS.ru says password/code sending can be used without legal-entity
  registration, contract, or sender approval in that simplified mode.
- SMS.ru also advertises up to 5 free SMS per day to the user's own number for
  some personal/programmer use cases. Treat this as useful for account testing,
  not as the production OTP plan.

Steps:

1. Confirm the account email in SMS.ru.
2. Copy `api_id` from the bottom of the SMS.ru main page or from the API
   section. Store it in a private password manager or local secret note, not in
   this repository.
3. Do not rotate/top up yet unless SMS.ru requires it for the first controlled
   OTP smoke.
4. Configure balance alerts and a low daily spend/volume limit before any broad
   testing.
5. Use `/sms/cost` for the current OTP message text.
6. Keep the OTP message short enough to fit one SMS segment where possible.
7. Add the controlled phone to the Stage 0 checklist.
8. Later, when staging env exists, set:

```text
SMS_BACKEND=smsru
SMSRU_API_KEY=<copied api_id>
```

Never commit the actual value.

Stage 0 gate:

- `api_id` exists.
- Account email is confirmed.
- Spend/volume limit is configured.
- Controlled phone is available.
- Current OTP message cost is known.

Sources:

- SMS.ru API docs:
  https://sms.ru/docs/api
- SMS.ru cost endpoint:
  https://sms.ru/docs/api/api_group_sms/cost
- SMS.ru public service page:
  https://sms.ru/

## 6. Yandex Maps

Goal: avoid a delivery launch that violates map/geocoder terms or creates an
unexpected large license bill.

This is the riskiest Stage 0 economic item.

Current Aura behavior:

- Customer address flows use Yandex Suggest and Geocoder.
- Typed addresses can be geocoded on save.
- The app stores address data and coordinates.

Important current facts:

- Yandex free terms prohibit storing data received from the API. Their example
  explicitly says you may not get data from Geocoder and save it to a database
  for future use; if you need to save data, they point to an extended paid
  version.
- Yandex commercial docs say the standard license does not allow saving or
  changing API data; the advanced license is for data preservation.
- The commercial JavaScript API + Geocoder page showed yearly pricing around
  `195,000 ₽/year` basic and `226,200 ₽/year` advanced for the `1000 requests/day`
  tier; it also showed a monthly basic tier of `20,800 ₽` for `1000 requests/day`.
  Verify inside the Yandex account/manager flow because product and region pages
  can differ.

Economical recommendation:

1. Do not pay for Yandex commercial license until we have written confirmation
   of the required license for Aura's exact data flow.
2. Do not launch delivery using free Geocoder if we persist Yandex-derived
   coordinates or canonical address data.
3. Ask Yandex support/manager whether Aura's flow requires advanced license:
   - customer enters address;
   - server geocodes it;
   - server stores address text, latitude, longitude, precision, and possibly
     canonical text;
   - server uses coordinates for delivery-zone validation and future order
     checkout.
4. If advanced license is too expensive for launch, choose one of these business
   paths before implementation:
   - launch pickup-only first;
   - keep delivery disabled until license is approved;
   - redesign delivery validation around a permitted data source or manual
     operator confirmation, which would require PDD/code changes.

Yandex API setup for Aura's current code:

Aura uses server-side keys for two server-proxied functions:

- Geosuggest/Suggest for address autocomplete:
  `https://suggest-maps.yandex.ru/v1/suggest`, configured with
  `YANDEX_MAPS_SUGGEST_API_KEY`.
- Geocoder for typed address validation:
  `https://geocode-maps.yandex.ru/1.x/`, configured with
  `YANDEX_MAPS_GEOCODER_API_KEY`.
- `YANDEX_MAPS_API_KEY` remains as an optional legacy/common fallback for local
  compatibility. Leave it empty in staging when split keys are configured.

Current state:

- Two Yandex keys have been created:
  - `JavaScript API и HTTP Геокодер`
  - `API Геосаджеста`
- This is the desired provider-side setup for Aura's split-key config.

Integration choice:

Use separate keys:

```text
YANDEX_MAPS_SUGGEST_API_KEY=<geosuggest_key>
YANDEX_MAPS_GEOCODER_API_KEY=<geocoder_key>
YANDEX_MAPS_API_KEY=
```

Configure the two keys this way:

1. Open the Yandex Maps API developer dashboard.
2. For the Geosuggest key, enable Geosuggest API / Suggest API.
3. For the Geocoder key, enable HTTP Geocoder.
4. Do not put the key into frontend code. Aura frontends call Core API; Core API
   calls Yandex.
5. For staging restrictions, prefer server IP restriction:
   - allowed IP: `212.8.226.214`.
6. If Yandex also asks for domains, add:
   - `https://staging.aura-coffee-bakery.ru`
   - later, only for production cutover:
     `https://aura-coffee-bakery.ru`
7. Wait up to 15 minutes after creating/changing the key before testing.
8. Store both keys privately. Later they go only into private staging env.

Do not add the main domain to Yandex restrictions until we actually point the
main domain at production.

Stage 0 gate:

- Yandex keys exist for testing.
- Integration choice recorded: Aura uses separate-key support.
- License/storage question has a written answer or a business decision.
- If the answer is "paid advanced required", owner approves cost or delivery is
  removed/deferred from launch scope.

Sources:

- Yandex free use terms:
  https://yandex.ru/dev/commercial/doc/en/
- Yandex JavaScript API + Geocoder commercial pricing:
  https://yandex.ru/dev/commercial/doc/en/concepts/jsapi-geocoder
- Yandex commercial FAQ:
  https://yandex.ru/dev/commercial/doc/en/concepts/faq

## 7. Controlled Test Phone

Goal: test real OTP without hitting customers or spending randomly.

Current decision:

- Use the developer's personal phone number for the first controlled OTP smoke.
- Do not commit or paste the actual phone number in docs, Git, screenshots, or
  chat.
- There is no Aura code setting for this yet. During the smoke test, type this
  number into the customer login form and verify the received OTP.
- SMS.ru "lists" and mailing setup are not needed for the first API OTP test.

Economical recommendation:

- Use the owner's phone or one cheap dedicated SIM.
- Avoid sending OTP repeatedly while debugging; the OTP worker is asynchronous,
  so wait for delivery state before retrying.
- Keep this number out of screenshots and logs.

Steps:

1. Pick one phone number.
2. Confirm it receives SMS reliably.
3. Use it for SMS.ru controlled tests.
4. Keep it in local/private launch notes, not public docs.

Stage 0 gate:

- Controlled phone is available during SMS testing windows.
- The actual number is stored privately, not in committed docs.

## 8. Legal, Privacy, And Fiscal Owners

Goal: assign accountable humans before real customer data and money flow through
the site.

Economical recommendation:

- Do not buy broad legal/compliance packages before the owner confirms the exact
  business model.
- Do assign an owner/accountant now, because these items can block launch.
- Keep initial legal scope narrow:
  - privacy policy;
  - personal-data processing consent;
  - public offer or terms for online orders;
  - refund/cancellation policy;
  - contact/business details;
  - 54-FZ receipt path;
  - personal-data operator notification/check.
- Avoid external analytics, ad pixels, chat widgets, and foreign processors
  until the personal-data story is clear.

Current legal checkpoints to confirm:

- 152-FZ personal-data operator notification or applicable exception.
- Russian data localization for Russian citizens' personal data.
- Personal-data security measures under 152-FZ Article 19.
- Published privacy/consent text before collecting phone/name/address.
- 54-FZ receipt path before online prepayment.

Stage 0 gate:

- Named owner for 152-FZ/privacy.
- Named owner/accountant for 54-FZ.
- Decision whether to use YuKassa receipt solution or separate online cash
  register.
- Legal page drafts are planned before public traffic.

Sources:

- 152-FZ Article 22 notification overview via Garant:
  https://base.garant.ru/12148567/94f5bf092e8d98af576ee351987de4f0/
- 152-FZ Article 19 security measures via Garant:
  https://base.garant.ru/12148567/95ef042b11da42ac166eeedeb998f688/
- Roskomnadzor personal-data portal notice from a regional RKN page:
  https://22.rkn.gov.ru/p10331/p32018/
- YuKassa 54-FZ receipt solutions:
  https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics

## Minimal Initial Budget Shape

These are not commitments; they are planning ranges from the current source
snapshot.

| Item | Stage 0 economical expectation |
|------|--------------------------------|
| `.ru` domain | Around `169-189 ₽/year` before renewal caveats. |
| TLS | `0 ₽` with Let's Encrypt. |
| VPS | Around `650 ₽/month` for 2 vCPU / 4 GB / 50 GB class; `1,100 ₽/month` for 4 vCPU / 8 GB class example. |
| YuKassa test shop | Should be usable before live contract; live fees need merchant-account confirmation. |
| YuKassa live payments | Current public fee page showed `2.8% + 1% for receipt` for common methods; verify before launch. |
| SMS.ru | Use `/sms/cost` for exact OTP message; start with small balance and daily limits. |
| Yandex Maps | Potentially `0 ₽` only if terms fit; Aura's persistent address/coordinate storage likely needs paid/advanced review. |
| Legal/accounting | Unknown; assign owner first, buy advice only for concrete questions. |

## Stage 0 Completion Checklist

- [x] Domain chosen and owner-controlled registrar account created:
      `aura-coffee-bakery.ru` on Beget.
- [x] `DOMAIN` and `staging.DOMAIN` DNS plan written.
- [x] VPS provider selected with monthly cost approved.
- [x] `staging.aura-coffee-bakery.ru` points to VPS IPv4 `212.8.226.214`.
- [ ] Production contact email and recovery path owned by the business.
- [x] YuKassa intentionally deferred; keep mocked until owner details are ready.
- [ ] YuKassa live onboarding owner assigned.
- [ ] 54-FZ receipt path owner assigned.
- [x] SMS.ru developer account created.
- [x] SMS.ru `api_id` visible in account UI; store privately, never in Git.
- [x] SMS.ru rotated `api_id` stored privately.
- [x] SMS.ru configured enough for Stage 0 developer smoke.
- [x] Controlled OTP test phone selected: developer personal phone, value
      private and not committed.
- [x] Yandex keys created for testing: Geocoder/JS key and Geosuggest key.
- [x] Yandex integration choice recorded: Aura uses separate-key code support.
- [ ] Yandex data-storage/license question sent or answered.
- [ ] Decision recorded: delivery at launch, pickup-only first, or delivery
      deferred.
- [ ] 152-FZ/privacy/legal owner assigned.
- [ ] Legal pages and consent text planned before public traffic.

## Deep Research Agent Prompts

Use these only if we want a deeper current-price/compliance refresh before
buying. Ask the agent to cite current official sources and capture screenshots
or archived URLs if available.

### Prompt 1: Domain And VPS Options

```text
Research economically reasonable domain and Russian VPS options for launching a
small production Docker Compose web app for a local coffee shop in Russia.

Context:
- App: Aura Coffee, one shop, customer SPA, admin SPA, FastAPI, PostgreSQL,
  Redis, Celery workers, nginx, media under /media/menu/.
- First-launch target: one VPS, Docker Compose, local Postgres/Redis, nginx on
  80/443 only.
- Minimum server target: Ubuntu 24.04, 2 vCPU, 4 GB RAM, 40-80 GB disk, static
  IPv4, Russian data center.
- Need reasonable personal-data due diligence; not a formal audit.

Deliver:
1. Table of 3-5 Russian VPS providers with current monthly prices for a
   comparable 2 vCPU / 4 GB plan and a 4 vCPU / 8 GB upgrade plan.
2. Whether each provider offers snapshots/backups, firewall, business invoices,
   Russian region, and any 152-FZ/security compliance claims.
3. Hidden-cost notes: IPv4, backups, traffic, support, VAT, renewal/price
   changes.
4. Recommended economical choice and why.
5. Domain registrar comparison for .ru: registration price, renewal price,
   DNS included, 2FA, ownership transfer process.
6. Cite official pricing/docs pages first; use comparison sites only as
   secondary evidence.
```

### Prompt 2: Yandex Maps Licensing And Alternatives

```text
Research the correct and economically reasonable map/address provider strategy
for Aura Coffee, a Russian local cafe ordering site.

Current app behavior:
- Customer enters delivery address.
- Frontend calls Aura Core API proxy.
- Server calls Yandex Geosuggest/Suggest and Geocoder.
- Server stores user delivery addresses, latitude, longitude, precision, and
  possibly canonical address text.
- Stored coordinates are reused for delivery-zone validation and checkout.

Questions:
1. Under current Yandex Maps API free terms, is storing Geocoder-derived
   coordinates/canonical addresses in Aura's database allowed?
2. If not, which paid/advanced license is required and what is the current
   lowest-cost option for a small public site?
3. Are there test keys or temporary testing permissions for closed staging?
4. What are current prices/limits for Geosuggest and Geocoder relevant to this
   use case?
5. What alternatives are practical in Russia for address suggest/geocoding with
   persistent storage allowed? Include DaData, 2GIS, OSM/Nominatim/self-hosted,
   or other credible options.
6. For each option, include cost, storage rights, Russian address quality,
   legal/commercial restrictions, and integration risk.
7. Recommend whether Aura should launch delivery immediately, launch pickup-only
   first, or pay for a provider license.

Cite official provider terms/pricing/support docs. Mark uncertainty explicitly.
```

### Prompt 3: YuKassa, Fiscalization, And SMS.ru Costs

```text
Research current economically reasonable onboarding for YuKassa and SMS.ru for
a small Russian coffee shop online ordering website.

Context:
- App takes prepaid online orders.
- Needs SMS OTP and order notifications.
- Needs YuKassa payment creation, webhook processing, refund/cancel path.
- Needs 54-FZ compliant receipts before live payments.

Deliver:
1. YuKassa onboarding steps for test shop and live shop.
2. Whether test shop can be used before contract/company docs.
3. Current public tariffs/commission for common payment methods and any receipt
   fee shown publicly.
4. Receipt/fiscalization options: Checks from YuKassa vs separate online
   cash register/cloud cash register; expected fixed and variable costs if
   publicly available.
5. Required business documents by entity type if available.
6. Refund fee/commission behavior if public docs state it.
7. SMS.ru onboarding: account, api_id, sender name, service-code mode, spending
   limits, balance alerts.
8. How to estimate SMS OTP cost using official endpoints before sending.
9. Recommended low-spend rollout: exact sequence and budgets.

Cite official YuKassa and SMS.ru pages first. Use secondary sources only for
gaps and label them as secondary.
```

### Prompt 4: Minimal Legal/Compliance Launch Checklist

```text
Research the minimal legal/compliance prerequisites for a small Russian cafe
online ordering website before collecting customer phone/name/address and taking
online prepayment.

Context:
- Website stores customer phone, name, delivery addresses, orders, payments.
- Production intended on Russian VPS.
- Payment via YuKassa.
- SMS OTP via SMS.ru.
- Delivery address validation via map/geocoder provider.

Deliver:
1. Personal-data operator obligations under 152-FZ: notification to
   Roskomnadzor, localization, policy, consent, security measures, incident
   notification if relevant.
2. Which items are likely mandatory before launch and which require lawyer
   confirmation.
3. Required public website documents: privacy policy, consent, public offer,
   refund/cancellation policy, contact/business info, cookie/analytics notice if
   analytics is used.
4. 54-FZ receipt obligations for internet payments and how YuKassa/check
   solutions may satisfy them.
5. Practical low-cost route: what the owner/accountant can do themselves vs
   what should go to a lawyer/accountant.
6. Red flags that should block live launch.

Cite official law/government/provider sources where possible. State clearly that
this is not legal advice.
```
