# Drinkit Public Screenshot Sources

Collected on 2026-05-01 for Aura Coffee design research.

These files are local reference material only. They are ignored by
`docs/design/screenshots/.gitignore` and must not be committed as Aura Coffee
assets. Use them to study flows, layout, density, hierarchy, motion expectations,
and interaction patterns. Do not copy Drinkit's logo, mascot, exact colors,
copywriting, proprietary product media, or distinctive trade dress.

## Search Scope

Public sources checked:

- [Apple App Store listing](https://apps.apple.com/us/app/drinkit-order-your-coffee/id1495622004)
- [Google Play listing](https://play.google.com/store/apps/details?id=ru.drinkit&hl=ru&gl=RU)
- [FoxData iOS listing mirror](https://foxdata.com/en/app-marketing-analytics/1495622004/as/US/)
- [FoxData Google Play listing mirror](https://foxdata.com/en/app-marketing-analytics/ru.drinkit/gp/US/drinkit/)
- [AppFollow iOS listing mirror](https://apps.appfollow.io/ios/drinkit-kofe-i-eda/1495622004?country=kr)
- [ScreenBook Drinkit iOS](https://screenbook.ru/app/drinkit-ios/?os=iOS)
- [Appvisor Drinkit page](https://appvisor.ru/app/ios/drinkit-kofe-i-eda-124441/)
- [VC article on visibility of system status](https://vc.ru/design/2055762-evristika-nilsena-vidimost-statusa-sistemy)
- [Habr/Dodo Engineering article on the payment slider](https://habr.com/ru/companies/dododev/articles/682846/)
- Drinkit Telegram and YouTube references surfaced by search, but were not
  bulk-downloaded because they are mostly marketing posts/videos and not
  clean in-app screenshot sources.

Important source notes:

- ScreenBook exposes some public images and gates the rest behind a paid
  subscription. Only public, non-subscription images were downloaded.
- Appvisor currently exposes useful app metadata and reviews, but its screenshot
  list is empty in the HTML at collection time.
- Store screenshots are marketing frames. ScreenBook and the existing pasted
  screenshots are more useful for real in-app state.

## Downloaded Files

All files below were saved under `docs/design/screenshots/`.

| File | Source | What It Shows |
| --- | --- | --- |
| `drinkit-appstore-2026-product-customizer-hero.png` | App Store/FoxData/AppFollow | English marketing frame for product detail with drink hero, nutrition strip, modifier tiles, size selector, add price pill |
| `drinkit-appstore-2026-modifier-grid-customization.png` | App Store/FoxData/AppFollow | English marketing frame for modifier grid and floating add-on cards |
| `drinkit-appstore-2026-cart-swipe-to-pay.png` | App Store/FoxData/AppFollow | English marketing frame for cart item quantities and bottom card-payment pill |
| `drinkit-appstore-2026-order-ready-status.png` | App Store/FoxData/AppFollow | English marketing frame for ready order status, notification, barista card, and tips |
| `drinkit-appstore-2026-shop-map-pickup-location.png` | App Store/FoxData/AppFollow | English marketing frame for map/shop picker and order-here CTA |
| `drinkit-appstore-legacy-product-customizer-photo.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for photo-led product detail and customizer |
| `drinkit-appstore-legacy-milk-temperature-toppings-selection.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for milk, temperature, topping, and syrup choice |
| `drinkit-appstore-legacy-favorite-drink-menu-card.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for favorite drinks and menu product card |
| `drinkit-appstore-legacy-order-accepted-notifications.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for accepted order state and push notifications |
| `drinkit-appstore-legacy-smart-pickup-shelf.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for smart pickup shelf numbers |
| `drinkit-appstore-legacy-invite-friends-profile-history.png` | App Store/AppFollow indexed legacy | Older Russian marketing frame for profile, invite friends, and order history |
| `drinkit-googleplay-2026-product-customizer-main.png` | Google Play | Russian marketing frame for product customization and add price pill |
| `drinkit-googleplay-2026-first-order-gift-vouchers.png` | Google Play | Russian marketing frame for first-order gift vouchers |
| `drinkit-googleplay-2026-modifier-grid-customization.png` | Google Play | Russian marketing frame for modifier grid and selected cards |
| `drinkit-googleplay-2026-referral-one-ruble-drink.png` | Google Play | Russian marketing frame for invite-a-friend/referral screen |
| `drinkit-googleplay-2026-cart-card-payment.png` | Google Play | Russian marketing frame for cart quantities and card-payment bottom bar |
| `drinkit-googleplay-2026-order-ready-tracking-tip.png` | Google Play | Russian marketing frame for order ready status and tip CTA |
| `drinkit-googleplay-2026-shop-map-order-here.png` | Google Play | Russian marketing frame for shop map and order-here CTA |
| `drinkit-screenbook-home-for-you-promo-usual-order-again.png` | ScreenBook | Real in-app home: top tabs, promo rail, personalized usuals, order again cards |
| `drinkit-screenbook-home-scrolled-worth-shot-new-for-you.png` | ScreenBook | Real in-app scrolled home: compact categories, "worth a shot", and large product card |
| `drinkit-screenbook-product-detail-matcha-customizer.png` | ScreenBook | Real product detail: media hero, favorite/close, add-ons, nutrition strip, fixed add CTA |
| `drinkit-screenbook-food-addon-grid-empty.png` | ScreenBook | Real add-on grid before selection |
| `drinkit-screenbook-food-addon-grid-selected.png` | ScreenBook | Real add-on grid with selected state and check/confirm affordance |
| `drinkit-screenbook-home-sticky-cart-bar.png` | ScreenBook | Real home with bottom sticky cart/payment bar |
| `drinkit-screenbook-catalog-black-coffee-boxes-coming-soon.png` | ScreenBook | Real category catalog with product availability and coming-soon cards |
| `drinkit-screenbook-product-detail-temperature-choice.png` | ScreenBook | Real product detail temperature bottom-sheet style selector |
| `drinkit-screenbook-order-rating-feedback-form.png` | ScreenBook | Real order rating form with positive/negative chips |
| `drinkit-screenbook-order-rating-fortune-cookie.png` | ScreenBook | Real order rating/fortune-cookie post-order screen |
| `drinkit-vc-status-visible-menu-header.png` | VC article | Cropped in-app menu/header used as system-status example |
| `drinkit-habr-menu-pay-slider-hero.jpeg` | Habr/Dodo Engineering | Older in-app product/menu screen with bottom pay slider |
| `drinkit-habr-payment-slider-states.png` | Habr/Dodo Engineering | Payment slider states: idle, in-progress, failed |
| `drinkit-habr-payment-error-feedback.png` | Habr/Dodo Engineering | Reported payment-slider error context with screenshot |

## Existing Local Screenshots

The pre-existing pasted set remains the deepest reference for current in-app
flows:

- `main_menu*.png` and `submenu*.png`: menu/category browsing and cart pill.
- `drink_page.png`, `drink_description.png`, and `drink_addons_*.png`: product
  detail, composition sheet, modifier groups, quantities, and selection states.
- `cart_and_checkout.png`: cart, upsells, receipt/photo/payment bar.
- `profile_deeper.png`: profile form and settings.

Together, the existing local screenshots plus this public set cover: home,
category, product detail, modifier selection, cart/payment, shop selection,
order status, rating, profile, referral, and older payment-slider behavior.
