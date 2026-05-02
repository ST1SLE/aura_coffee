# Aura Coffee ordering redesign direction

## Executive design thesis

Aura should **not** become “another dark coffee app.” The attached PDF reads more like a restrained brand poster than a typical cafe UI: a muted sage/olive field, a white rounded geometric AURA mark, a compact uppercase category line, and a handwritten Cyrillic slogan with almost no extra decorative vocabulary. The local adaptation notes and current CSS, by contrast, are oriented around a dark, cinematic, Drinkit-like shell with near-black surfaces, a gold primary, a teal accent, and `color-scheme: dark`. The right move is therefore **a soft botanical ordering utility**: warm cream as the main working canvas, sage as the brand field, espresso as the default text color, and product media as the main merchandising layer. That keeps the PDF as the source of truth while rejecting the generic “dark brown coffee” and “startup neon” traps you explicitly want to avoid. fileciteturn0file3 fileciteturn0file0L3-L5 fileciteturn0file4L6-L25

This direction follows the PDF in the most important way: it preserves **Aura’s calm, poster-like identity** while keeping the first screen useful for browsing and ordering. The logo and slogan become high-value brand signatures, not everyday interface text. The ordering experience stays fast, mobile-first, and media-led, but the visual tone shifts from “tech coffee app” to **“specialty cafe with patisserie warmth and clear commerce.”** That makes Aura feel more local, more ownable in Russian and English, and more compatible with delivery/pickup, cart, checkout, status, and profile flows. fileciteturn0file0L13-L20 fileciteturn0file2L38-L40

The core rule is simple: **brand atmosphere in the frame, operational clarity in the controls**. Use the sage world to set tone and memory; use cream, espresso, and high-contrast surfaces to let people actually place an order. This matters because WCAG still requires normal body text to meet minimum contrast, and the poster-like white-on-sage treatment that works for a logo does not work for small functional UI copy. entity["organization","W3C","web standards body"] citeturn14search6turn14search1turn23search0

## Visual identity translation

The PDF implies a **two-voice brand system**, not a large kitchen-sink design language: one voice is geometric, compact, and modern; the other is human, handwritten, and emotional. The website should preserve that asymmetry. The geometric voice becomes the UI’s structural language. The handwritten voice becomes a controlled accent. Everything else should stay quiet. fileciteturn0file3

**What should remain brand or art only**

- The white rounded AURA mark should stay a **logo lockup**, loading splash, order-status header, packaging stamp, or empty-state signature, not a repeated button shape or repeating decorative pattern. fileciteturn0file3
- The handwritten Cyrillic slogan should stay an **art asset** for a homepage corner, seasonal banner, packaging insert, or closed-store poster. It should **not** become nav text, button text, category labels, or form language. Images of text are acceptable when the presentation is essential to branding, but ordinary information should stay real text. citeturn23search0turn23search9
- The compact uppercase category style from the PDF is excellent for **micro-labels**: section overlines, category chips, delivery/pickup labels, “NEW,” “POPULAR,” “SOLD OUT,” and small card metadata. It should not be used for paragraphs, product descriptions, form helper text, or long address content. Heavy all-caps hurts readability when overused. citeturn12view4turn6search12

**What should become functional UI**

- Product names, modifiers, addresses, price totals, checkout labels, and error text should use mixed-case, high-contrast text on cream or warm neutral surfaces. citeturn14search6turn14search1
- The sage anchor should appear as **framing**: the top shell, selected state families, empty states, status cards, or editorial blocks. It should not be the default background for every card and every form. fileciteturn0file3
- The site should feel like **a poster wrapped around a fast ordering engine**, not like a poster forced on top of one. That means brand moments at the edges, and sober UI in the middle. fileciteturn0file2L42-L52

My strongest opinion here is that **Aura’s home should not open with a giant marketing hero**. The first screen should open with the order context: fulfillment mode, store status, search, categories, and orderable cards. The poster energy belongs in the shell and the media, not in a landing-page intro that slows down ordering. That is consistent with the local adaptation notes, which emphasize menu-first structure, persistent cart reachability, visible order state, and fast customization. fileciteturn0file0L15-L19 fileciteturn0file0L66-L74

## Typography and color system

**Recommended production pairing: Onest + Inter**

This is the best balance of brand fit, Cyrillic quality, implementation ease, and ordering clarity. **Onest** is explicitly described as suitable for apps and sites, readable in small interface sizes, and supportive of Cyrillic and Latin. **Inter** is a mature interface workhorse with 2,000+ glyphs, 147-language coverage, optical sizing, and strong numeric behavior for prices, totals, and order numbers. Both are open-source, available through Google Fonts, and easy to self-host through Fontsource with Cyrillic subsets. citeturn29view3turn29view4turn30view1turn29view0turn30view0

Use that pair like this:

- **Headings and section labels:** Onest 700–800. It gives Aura a slightly squarer, calmer, less-generic tone than Inter alone. citeturn29view3turn29view4
- **Category rail, CTA labels, chips, and short metadata:** Onest 600, with modest tracking for all-caps micro-labels. citeturn29view3turn29view4
- **Body copy, product descriptions, modifiers, forms, addresses, checkout fields:** Inter 400–500. It is safer in dense bilingual UI and stronger for long operational text. citeturn29view0turn30view0
- **Prices, totals, order numbers, promo math:** Inter 600–700. Let the numeric system stay boring and precise. citeturn29view0

**Other viable pairings**

- **Manrope + Golos Text** — a little more polished and softly geometric. Manrope supports Cyrillic and ships easily via Fontsource; Golos Text was built for screen reading and released under OFL. This is a good option if you want slightly more “brand polish” and slightly less utilitarian feel than Onest + Inter. citeturn29view1turn31search0turn29view2
- **Inter only** — the lowest-risk implementation path. If engineering speed is the priority, Inter can carry the whole product without looking wrong. It just feels less specifically “Aura” than a two-font system. citeturn29view0turn30view0
- **TT Norms Pro + Inter** — the premium commercial route. TT Norms Pro is a strong retail grotesk with Cyrillic support, but it requires a paid web/app license from entity["company","TypeType","type foundry"]. Use this only if you want to invest in a more distinctive paid type system. citeturn16search1turn5search7
- **Graphik + Inter** — elegant and proven, but expensive and not necessary for Aura’s first strong implementation. If budget is tight, the free options above are already good enough. entity["company","Commercial Type","type foundry"] citeturn16search2turn16search9

**Licensing and hosting notes**

- Onest, Inter, Manrope, and Golos Text are practical for both Google Fonts delivery and self-hosting via Fontsource. Fontsource explicitly supports self-hosting, version locking, privacy, and offline use. citeturn18search7turn30view0turn30view1turn31search0turn29view2
- I would strongly prefer **self-hosting** in a React/Tailwind codebase, because it reduces dependency drift and keeps the bilingual UI stable release to release. citeturn18search7
- Do **not** introduce a handwriting font to imitate the slogan. Keep the actual slogan as a deliberate brand asset instead. citeturn23search0turn23search9

**Recommended semantic palette**

The safest palette is a **split system**: poster sage for brand fields, cream for work surfaces, espresso for text, caramel/pastry tones for appetite and emphasis.

- `brand.sage = #93A27C` — approximate anchor lifted from the rendered PDF; use for header fields, brand panels, and empty states, not dense white text. fileciteturn0file3
- `brand.sage.deep = #6C7A55` — selected chips, sticky cart background, primary brand buttons where white text is required.  
- `canvas.cream = #F6F1E7` — default page background for menu, cart, checkout, profile.  
- `surface.warm = #ECE4D6` — nested cards, sheets, order summary panels, subtle sections.  
- `text.espresso = #1B1713` — default text and icon color.  
- `text.bark = #3A2E25` — secondary text, helper copy, dividers.  
- `accent.caramel = #B9783F` — price emphasis, selected modifier edge, seasonal highlights; not paragraph text.  
- `accent.pastry = #D8B08C` — soft badges, skeleton tint, promo chips.  
- `border.olive = #B7C2A8` — borders, separators, inactive chips, field edges.  
- `status.success = #446347` and `status.error = #A34F35` — operational states that still fit the muted Aura palette.

**Contrast rules**

The single biggest accessibility trap is the obvious one: **white on the PDF sage**. Against the recommended poster sage, white is only about **2.7:1**, which fails AA for normal text. Against the deeper action sage, white rises to about **4.6:1**, which is acceptable for regular CTA text. So the safe rule is: **espresso on poster sage, white only on deep sage.** WCAG still requires at least **4.5:1** for normal text, **3:1** for large text, and **3:1** for essential UI components and graphics. citeturn14search6turn14search1turn14search17

The practical implication is that the PDF sage should behave like a **brand substrate**, not like a universal background token. It works beautifully behind the logo, headings, empty states, and high-level shells. It is much weaker behind form labels, small tab text, or cart totals unless the text is dark. That one decision will determine whether Aura feels premium or simply hard to read. fileciteturn0file3 citeturn14search6turn14search1

## Component direction

**App shell and header**

Make the home shell feel like a native ordering product, not a brochure. The top should contain only what helps ordering: fulfillment mode, current store status, location/address confirmation, search, and profile/cart access. Keep the logo lockup compact. The first visible menu content should appear fast, with categories and orderable cards within the first screen. This fits the local packet plan and the menu-first guidance in the design notes. fileciteturn0file2L177-L190 fileciteturn0file0L34-L47 fileciteturn0file0L66-L74

**Menu category rail**

Use a sticky horizontal category rail directly under the header. Categories should use the PDF’s compact uppercase spirit, but only at micro-label scale. Selected state: deep sage fill with white text. Unselected state: cream chip with espresso text and olive border. Categories should come from the API, not invented editorial buckets unless the metadata already supports them. fileciteturn0file0L58-L74

**Product cards**

Cards should be **media-first** but not overdesigned. Use a strong image or poster frame, a two-line max product name, a stable price line, and a clear add control within thumb reach. The card body should stay light and quiet so pastries, desserts, and breakfasts can show texture and color. Keep “new,” “popular,” “sold out,” or dietary tags in small uppercase chips, never in giant promo slabs. The local benchmark is right that media is the main sales/navigation tool, but Aura should express that in a lighter, warmer frame. fileciteturn0file0L15-L16 fileciteturn0file0L60-L64

**Item detail and customization**

On mobile, the item detail should open as a tall sheet or page with a strong hero image/video at the top, then product facts, then a visual modifier system, with the main add-to-cart summary anchored at the bottom. Keep modifiers visually tactile, but do not invent grouped categories or per-modifier quantities unless product scope expands. The local notes are explicit that Aura’s current modifier model is flat and that grouped behaviors are a product/API change. fileciteturn0file0L105-L119 fileciteturn0file0L130-L145

**Sticky cart**

Keep a persistent cart bar once items exist. It should show item count, total, and the current fulfillment promise, and it should stay safe-area aware on mobile. Use tap-first checkout. Do **not** start with swipe-to-pay on the web. Drinkit’s own internal write-up shows that a swipe control required teaching animations, haptics, multiple failure states, and careful cross-screen synchronization to avoid accidental or duplicate actions. Aura’s web product should earn that complexity later, not inherit it on day one. fileciteturn0file0L158-L173 citeturn25view0

**Checkout**

Checkout should be a single-scroll, sectioned surface, not a maze. Use distinct cards for fulfillment, address, time, payment, notes, and summary. Keep pricing, discounts, delivery fees, payment creation, and status interpretation server-owned. Make the current mode visible at every step so the user never forgets whether they are checking out for pickup or courier delivery. That is consistent with the existing project boundaries and avoids accidental backend/product drift. fileciteturn0file2L74-L88

**Profile, orders, and loyalty**

Keep profile and orders visually subordinate to menu/cart/checkout. Orders should use clear ready/in progress/delivered states, with the most recent order surfaced first and reorder visible where the API already supports it. Loyalty should only appear if the current product already supports it; the local guidance explicitly treats referral gifts, tips, ratings, and loyalty expansions as product changes rather than purely visual work. fileciteturn0file0L193-L199 fileciteturn0file0L235-L247 fileciteturn0file2L85-L88

**Empty, loading, and error states**

Use Aura’s most poster-like moments here. An empty cart, closed store, unavailable fulfillment mode, or temporary error can carry the sage field, logo lockup, and even the handwritten slogan. But loading states for normal commerce should still be operational: skeleton cards, clear retry affordances, and precise reasons. The local checklist is right to insist that unavailable and failed states explain what happened, and the Drinkit slider post is a good reminder that payment errors and unavailable products must surface in-place, not in mysterious dead ends. fileciteturn0file0L273-L280 citeturn25view0

## Photography, video, and art direction

Aura should treat product media as **the primary selling surface**. That is fully aligned with the local design notes and with best-practice merchant guidance from entity["company","DoorDash","delivery platform"] and entity["company","Uber Eats","delivery platform"], which both emphasize accurate single-item framing, centered composition, clean backgrounds, and images that actually represent what customers can buy. fileciteturn0file0L15-L16 fileciteturn0file2L44-L50 citeturn26view0turn26view2turn26view3

**Photography rules**

- Use **real or Aura-generated owned media only**. No third-party cafe brand media, no downloaded Drinkit visuals, no stock latte art that belongs to another brand world. Merchant guidelines also explicitly require that the business own or have rights to use the images. fileciteturn0file0L221-L222 citeturn26view3
- Use **indirect natural light** or soft controlled light. Avoid hard fluorescent cast, harsh noon sunlight, oily specular hotspots, or muddy dark-brown grading. Food should look fresh, not “moody.” citeturn26view2turn8search4
- Use **top-down** for breakfast plates, pastries, flat desserts, and bowls; use a **45-degree angle** for cups, layered desserts, sandwiches, and taller items. citeturn26view2
- Keep the **item centered and recognizable**, with enough margin for crop safety across menu cards and detail headers. Do not overlay text or graphics on item imagery. citeturn26view0turn26view3
- Backgrounds should feel like Aura materials: cream stone, pale tabletop, warm tile, matte ceramic, linen, or lightly grained wood. They should support the sage UI, not fight it.

**How this should look for Aura specifically**

For coffee: close enough to show texture, crema, foam pattern, cup material, and condensation if iced, but not so close that cup size becomes unclear. For pastries and desserts: show full item shape and crumb/icing detail. For breakfast items: favor portion clarity and ingredients over stylized blur. The visual mood should be **quiet appetite**, not glossy ad-world maximalism. citeturn26view0turn26view2

**Video guidance**

If Aura goes video-first, use **short, silent, looped clips** for homepage feature cards and item detail heroes only. Do not autoplay video across the entire catalog. The project README correctly separates a safe visual pass from a real media-contract change, and it already calls for autoplay rules, lazy loading, poster fallbacks, and reduced-motion handling if video becomes a product capability. Respect `prefers-reduced-motion`, because users can explicitly request reduced motion. fileciteturn0file2L119-L160 citeturn12view2turn12view3

**Where illustration belongs and where it does not**

Illustration belongs in promotional/editorial moments, empty states, or seasonal inserts. It does **not** belong as a substitute for orderable product media. The PDF gives Aura enough personality already; the site does not need a mascot, whimsical ingredient doodles, or a fake handcrafted visual layer to prove it is a coffee brand. Keep illustration at the edges and keep product media honest in the center. fileciteturn0file3 fileciteturn0file2L54-L60

## UX benchmark findings

**entity["company","Starbucks","coffee chain"]**  
Borrow: saved-store/payment maturity, explicit store metadata, view-past-orders logic, and the new scheduled pickup option that lets customers choose a pickup window in checkout. Avoid: recreating its rewards-heavy promotional density or letting marketing modules outrank ordering. Aura should use Starbucks’ operational clarity, not its scale-driven merchandising sprawl. citeturn9view0turn9view1turn10view2

**entity["company","Costa Coffee","coffee chain"]**  
Borrow: its very clear “order ahead, pay, collect, no need to queue” mental model and the simple step-by-step click-and-collect explanation. Avoid: a home experience that explains ordering instead of letting the user order. In Aura, the same clarity should exist, but the product should open directly into browse/order flow. citeturn9view2turn10view0

**entity["company","Blue Bottle Coffee","coffee roaster"]**  
Borrow: the thoughtful premium feel of “your personal barista,” the orderly customizer, pay-ahead flow, and the cafe finder with hours and descriptions. Avoid: making the interface so sparse or editorial that price, add actions, and fulfillment cues become too quiet for a pastry-and-breakfast ordering product. citeturn9view3turn28view0

**entity["company","Blank Street Coffee","coffee chain"]**  
Borrow: one-click signup and payment, ready notifications, delivery support, and a lightweight seasonal layer that sits on top of commerce instead of replacing it. Avoid: drifting into Blank Street’s specific “green, green, green” identity or borrowing its brand posture too literally. Aura already has a green anchor; the challenge is to make it Aura’s green, not Blank Street’s. citeturn10view1turn19view0

**entity["company","Joe Coffee","ordering platform"]**  
Borrow: the separation of discovery, ordering, and rewards; desktop/mobile parity; real-time order status; and support for pastries and bakery items alongside coffee. Avoid: importing multi-shop discovery complexity into a single-shop Aura flow. Joe is a useful systems benchmark, not a direct IA model. citeturn9view5turn10view3

**entity["company","Drinkit","coffee app"]**  
Borrow: media-led menu hierarchy, customization prominence, designated pickup-slot thinking, sticky cart/payment reachability, and strong post-order status visibility. Avoid: its dark tech shell, gift/referral surface area, and gesture-heavy payment flourish as a default web pattern. Drinkit is valuable because it proves that coffee ordering can feel fast and ritualized; it is dangerous because its brand world and product feature set are much broader than Aura’s current scope. fileciteturn0file0L13-L28 citeturn27view0turn27view1turn27view2turn25view0

**entity["company","Skuratov Coffee","russian roaster"] and entity["company","Surf Coffee","russian coffee chain"]**  
Borrow from Skuratov: direct local utility, visible store hours, menu access, and a matter-of-fact Russian-language tone that feels local rather than over-marketed. Borrow from Surf only the idea that loyalty can carry emotional/cultural weight. Avoid both brands’ worlds as design templates: Skuratov can become sprawling when many locations are in play, and Surf’s surf-culture identity is too distinctive and too lifestyle-led for Aura’s ordering-first goal. citeturn11view3turn11view1turn11view2

**entity["organization","European Coffee Trip","coffee guide"]**  
This is a moodboard-quality regional context source, not an ordering benchmark. Borrow its specialty-coffee photography quality and location-led European cafe sensibility. Do not borrow its content architecture for Aura’s transactional product. citeturn19view2

## Implementation implications

The first thing to change in the codebase is **not** the page layout. It is the **token layer**. The current `index.css` encodes a dark-mode-first design language that is structurally far closer to the local Drinkit adaptation than to the Aura PDF. Replace those semantic values first: background, card, primary, accent, border, ring, and radius. Only after the color and type system are correct should you restyle screens, because otherwise every later component decision will be biased by the wrong visual gravity. The local README also explicitly recommends updating `src/index.css`, Tailwind classes, and existing primitives before adding abstractions. fileciteturn0file4L6-L25 fileciteturn0file2L162-L175

If the project is already on Tailwind v4, define Aura’s palette and fonts with `@theme` so they generate utility classes and runtime CSS variables together. That is now the official Tailwind path for colors, fonts, tracking, breakpoints, and related design tokens. If the project is still effectively using a semantic CSS-variable layer, keep the semantic names and swap their values first rather than hard-coding Aura colors component by component. citeturn17view0turn17view1turn17view2

After tokens, rebuild the **smallest durable primitives** first:

- header shell  
- category chip/rail  
- product card  
- modifier tile  
- sticky cart bar  
- checkout section card  
- status badge

Once those exist, apply the local packet sequence: shell, menu/product cards, item detail, cart, checkout, then orders/profile. That sequence already matches the project’s own recommended implementation path. fileciteturn0file2L177-L190 fileciteturn0file0L257-L269

What should be **preserved** is equally important: route paths, current API payloads, server-owned pricing/totals/delivery fees, server-owned order and payment states, i18n keys, tests, and PII safeguards. The local docs are explicit that visual redesign alone should not create backend work unless a change is truly a product behavior change. That means loyalty, grouped modifiers, video media contracts, ratings, gifts, and new order states need their own product decisions if they move beyond presentation. fileciteturn0file2L74-L88 fileciteturn0file2L214-L220 fileciteturn0file0L235-L247

The redesign should be validated with **screenshots first**, not just with component snapshots. The project README already calls for comparison at realistic mobile widths like 375px, 390px, and 430px, and the local screenshot inventory covers the key flows you need to mirror: home, category, product detail, modifiers, cart/payment, order status, and profile. For Aura, I would specifically validate these states in both Russian and English: long product names, long modifier sets, sold-out items, empty cart, checkout with keyboard open, pickup vs courier address entry, order-ready state, payment failure, and reduced-motion media fallback. fileciteturn0file2L202-L208 fileciteturn0file1L61-L74 fileciteturn0file1L76-L89

The biggest implementation risks are straightforward. **Bilingual expansion** can break compact category labels and checkout rows. **White-on-sage** can silently fail accessibility. **Sticky bottom controls** can collide with safe areas and mobile browser chrome. And **gesture-heavy checkout ideas** can create hidden error states faster than they create delight. The safest interpretation of the benchmark research is to keep Aura visually distinctive and operationally conservative: high-quality media, beautiful cards, clear tap targets, explicit state labels, and no invented magic. fileciteturn0file2L171-L175 fileciteturn0file2L217-L220 citeturn14search6turn14search1turn12view1turn25view0

**Open questions and limitations**

- I could inspect the PDF visually, but I could not extract an exact font identity from it, so the typography recommendations are based on fit, support, licensing, and current best practice rather than a one-to-one type match. fileciteturn0file3
- The local docs describe both a safe image-first visual pass and a richer owned-video path. If Aura is staying image-only in the near term, some media recommendations should be treated as future-ready rather than immediate scope. fileciteturn0file2L119-L160
- I do not have the full Tailwind config, so the token migration advice assumes either Tailwind v4 `@theme` or a semantic variable layer similar to the current `index.css`. fileciteturn0file4L1-L25 citeturn17view0turn17view1

## Source list

- **Aura brand PDF, local adaptation guide, project README, and current CSS** — the primary sources for Aura’s intended identity, implementation boundaries, screenshot workflow, and the currently mismatched dark interim shell. fileciteturn0file3 fileciteturn0file0L3-L28 fileciteturn0file2L36-L88 fileciteturn0file4L6-L25
- **Starbucks official ordering pages and app listing** — best source for current large-scale order-ahead, scheduled pickup, store metadata, saved orders, and payment maturity. citeturn9view0turn9view1turn10view2
- **Costa official click-and-collect page and app listing** — strong benchmark for queue-skipping clarity and integrated loyalty. citeturn9view2turn10view0
- **Blue Bottle official app listings** — premium specialty-coffee benchmark for streamlined order-ahead and calm customization. citeturn9view3turn28view0
- **Blank Street official site and app listing** — useful benchmark for light seasonal merchandising and fast order-ahead behavior without overloading the flow. citeturn19view0turn10view1
- **Joe official site and app listing** — helpful systems benchmark for reorder, order status, coffee-plus-bakery support, and cross-device flow parity. citeturn9view5turn10view3
- **Drinkit official site and app listings plus the Dodo Engineering Habr article** — the most relevant local benchmark for media-led coffee ordering and the clearest cautionary source on swipe-to-pay complexity. citeturn27view0turn27view1turn27view2turn25view0
- **Skuratov, Surf, and European Coffee Trip** — useful for Russian and broader European specialty-cafe context, local tone, location utility, loyalty framing, and photography taste. citeturn11view3turn11view1turn11view2turn19view2
- **Google Fonts, Fontsource, Inter, Onest, Manrope, Golos Text, and commercial foundry references from entity["company","Paratype","type foundry"] and TypeType** — the basis for Cyrillic support, licensing, self-hosting, and production-friendly typography choices. citeturn29view0turn29view1turn29view2turn29view3turn30view0turn30view1turn31search0turn18search7turn16search1turn5search7
- **W3C and MDN accessibility guidance** — the basis for contrast, target size, capitalization, reduced motion, and images-of-text recommendations. citeturn14search6turn14search1turn12view1turn12view2turn12view3turn12view4turn23search0turn23search9
- **DoorDash and Uber merchant photo guidance** — the clearest practical rules for menu photography framing, authenticity, backgrounds, light, crop, and image ownership. citeturn26view0turn26view1turn26view2turn26view3
- **Tailwind docs and react-i18next docs; research context from entity["organization","Baymard Institute","ux research"]** — operational references for tokenizing the design system and preserving bilingual UI discipline during implementation. citeturn17view0turn17view1turn17view2turn17view4turn6search2turn6search6