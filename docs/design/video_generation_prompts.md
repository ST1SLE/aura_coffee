# Aura Coffee Video Generation Prompts

This document defines reusable prompts for generating Aura-owned drink videos for
the customer menu and item-detail surfaces.

The prompts are written for mobile-first video generation. They intentionally do
not include app UI, text, prices, nutrition labels, buttons, status bars, or
phone chrome. Aura Coffee overlays those elements in the frontend.

## Target Output

- Primary format: vertical `9:16`.
- Recommended source size: `1080x1920` or higher.
- Duration: `5 seconds`.
- Motion plan: first `1.0-1.3 seconds` preparation motion, then finished drink
  hero motion.
- Playback: muted, smooth, loop-friendly.
- Composition: drink centered and fully readable on mobile, while still working
  when cropped into a horizontal menu card.
- Asset location convention:
  `/media/menu/{item-slug}/hero.mp4` and
  `/media/menu/{item-slug}/poster.webp`.

## Visual Direction

Aura Coffee should feel like a real local coffee shop, not a generic fantasy
render. Use a premium but grounded cafe look:

- light wooden table;
- warm daylight from a window;
- muted olive, beige, grey, and soft cream tones;
- shallow depth of field;
- blurred cafe background with optional window, plant, ribbed vase, grey sofa,
  or relief wall texture;
- realistic glass transparency, liquid physics, foam, crema, condensation,
  shadows, and reflections.

The reference direction favors videos where the drink is the only hero object,
with either:

- a short preparation moment, such as espresso, milk, foam, or topping being
  added; then
- a calm hero shot where the finished drink slowly rotates, or the camera
  slowly orbits/pushes around the drink while the background moves subtly.

## Mobile And Desktop Safe Areas

The same video may be used on several surfaces:

- mobile menu card;
- desktop menu card;
- mobile item detail hero.

Because the frontend overlays content, keep the asset clean and crop-safe:

- Keep the main drink inside the central `45-60%` of the frame width.
- Keep the drink body mostly between `25%` and `72%` of frame height.
- Avoid important details in the top `15%`, bottom `22%`, or outer `8%` edges.
- Put the most recognizable finished-drink frame near seconds `2.0-4.5`; this
  makes poster-frame extraction easier.
- Avoid rapid movement, large splashes, or big camera shifts near the edges.
- For desktop card crops, the drink should still read if the top and bottom are
  cropped and only the central horizontal band remains.

## Base Template Prompt

Use this template first, then replace bracketed fields for the specific drink.

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video.
- 5 seconds.
- Smooth, premium commercial drink cinematography.
- Muted, loop-friendly, no sound-dependent action.
- No app UI, no status bar, no captions, no labels, no prices, no nutrition
  text, no buttons, no visible watermark.

Drink:
- Name: [DRINK_NAME].
- Vessel: [VESSEL_DESCRIPTION].
- Match the vessel shape closely: [REFERENCE_GLASS_OR_CUP_DETAILS].
- Liquid appearance: [LIQUID_COLOR_AND_OPACITY].
- Layers: [LAYER_DESCRIPTION_OR_NONE].
- Top surface: [FOAM_CREMA_LATTE_ART_TOPPING].
- Temperature cues: [STEAM_FOR_HOT_DRINK_OR_CONDENSATION_FOR_COLD_DRINK].

Scene:
- Real cozy modern cafe interior.
- Light wooden table.
- Warm natural daylight from a window, mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream color palette.
- Background softly blurred with subtle parallax: [BACKGROUND_DETAILS].
- Optional real Aura-style props only if subtle: ribbed glass vase, small green
  plant, grey sofa, relief wall texture, window light.
- No people, no hands, no extra drinks competing with the hero drink.

Camera and motion:
- Begin with a close preparation moment for the first 1.0-1.3 seconds:
  [PREPARATION_ACTION].
- The preparation action should be elegant and physically realistic: a smooth
  pour, foam settling, ice shifting, crema forming, or topping falling.
- During preparation, the drink must evolve continuously and physically. Liquid
  color, level, foam, ice, and toppings should change gradually from frame to
  frame. Do not let a dark drink suddenly become pale, a clear drink suddenly
  become opaque, or an unfinished drink suddenly become finished in one frame.
- Motion continuity is mandatory. When the pour or topping action ends, it must
  taper naturally: the stream exits the frame or narrows gradually, liquid
  ripples continue, foam keeps settling, ice shifts slightly, steam drifts, and
  reflections keep moving. Do not let the video switch from active pouring to a
  perfectly still drink in a single frame.
- After 1.3 seconds, transition into the finished drink hero shot. If this is a
  cut instead of one continuous shot, make it read as a deliberate cinematic cut:
  the framing or camera distance may change, but the same vessel, drink color,
  amount of liquid, foam, toppings, and motion direction must remain physically
  consistent. No frozen transition frame and no sudden stop between preparation
  and hero shot.
- From 1.3-5.0 seconds, the finished drink slowly rotates on the table OR the
  camera slowly orbits/pushes around it. This hero motion begins gradually while
  the liquid surface is still settling; it should not start after a visible
  freeze.
- Camera motion is slow, stable, and premium. No shake, whip pan, zoom jump, or
  sudden reframing.
- Background movement should be subtle and blurred, never more important than
  the drink.

Composition:
- Mobile-first composition.
- Keep the full drink centered and readable.
- Main drink body stays mostly between 25% and 72% of frame height.
- Leave clean space at the top for app overlays.
- Leave clean space at the bottom for app controls.
- Keep all important drink details away from the outer edges.
- The same video should still look good if cropped into a horizontal menu card.

Rendering quality:
- Photorealistic glass, ceramic, foam, liquid, shadows, and reflections.
- Accurate scale: one drink, normal cafe cup/glass size.
- Realistic transparency through glass.
- Realistic ribbed-glass refraction when using a ribbed glass.
- Temporal consistency across the full clip: same vessel shape, same drink
  volume, same ingredient colors, and believable continuity from preparation to
  finished hero shot.
- Temporal motion consistency across the full clip: liquid, foam, ice,
  condensation, steam, reflections, and camera/parallax motion continue
  naturally. The finished hero shot may be calm, but it must not become a
  static still image immediately after the pour.
- When milk, espresso, syrup, foam, or cream is poured, the visible liquid must
  blend naturally. Color changes should be progressive, not a jump cut or
  magical replacement.
- Natural color grading, not oversaturated.
- Clean appetizing surface, no mess.

Negative prompt:
- Do not generate text, menu UI, phone UI, nutrition values, prices, buttons, or
  icons inside the video.
- Do not generate people, faces, hands, fingers, arms, branded third-party
  packaging, random logos, or extra cups.
- Do not distort the glass or cup.
- Do not make the vessel melt, wobble, change shape, duplicate, float, or
  disappear.
- Do not create single-frame color jumps, liquid morphs, instant ingredient
  replacement, or a finished drink appearing suddenly in the same composition.
- The video must show one smooth, continuous drink lifecycle in real time:
  preparation begins, liquid rises/blends, the pour tapers, surface motion
  continues, foam/ice/steam keeps settling, and the hero rotation or camera move
  continues without interruption.
- Do not create a time-skip between pouring/mixing and the finished drink. Do
  not cut from an active pour to a perfectly complete still drink as if a minute
  passed.
- Do not create an abrupt freeze after the pour, a still-frame hero shot, or a
  sudden stop of liquid, foam, ice, steam, reflections, camera motion, or
  background parallax.
- Do not create impossible liquid behavior, violent splashes, floating
  ingredients, smoke clouds, fantasy effects, cartoon style, plastic-looking
  foam, or artificial neon lighting.
- Do not crop off the drink.
- Do not place the drink too low, too high, or too close to the frame edges.
```

## Cappuccino Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium commercial drink footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Cappuccino.
- Vessel: short clear ribbed glass, cylindrical with vertical grooves and a
  heavy transparent base, inspired by Aura's real ribbed glass references.
- The glass must look like real transparent glass, with believable refraction,
  highlights, rim thickness, and shadow.
- Liquid: warm caramel-brown espresso and milk mixture.
- Foam: dense creamy milk foam forming a smooth top layer.
- Top surface: simple white heart latte art centered on the foam.
- Hot-drink cue: very subtle steam only, thin and realistic, not smoky.

Scene:
- Light wooden cafe table.
- Warm beige-to-caramel background with a softly blurred modern cafe interior.
- Subtle Aura-style environment details: muted olive/grey tones, soft window
  daylight, relief wall texture or grey sofa in the blur.
- Background stays soft and premium, not busy.

Video sequence:
- 0.0-1.2 seconds: close preparation moment. A smooth white stream of steamed
  milk pours into the espresso inside the ribbed glass. The pour creates a
  realistic creamy swirl and starts forming foam. Do not show hands; only the
  milk stream and part of a simple metal pitcher may appear at the top edge if
  needed.
- 1.2-5.0 seconds: finished cappuccino hero shot. The glass is now full with a
  clean foam cap and heart latte art. The finished drink slowly rotates on the
  table, or the camera slowly orbits around it by a few degrees.
- Foam and reflections move subtly. Steam remains delicate.

Composition:
- Keep the glass centered.
- The full rim, foam, and base remain visible.
- Main glass body stays mostly between 25% and 72% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still look good when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, fingers, faces, extra drinks, random logos, or third-party
  branding.
- No distorted glass, warped rim, duplicate glass, floating cup, unrealistic
  splashes, giant steam cloud, messy table, or cartoon style.
- Do not make the latte art too complex, asymmetrical, blurry, or distorted.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  foam settling, steam, reflections, rotation, or camera motion.
```

## Americano Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth, minimal, premium coffee product cinematography.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Americano.
- Vessel: tall clear ribbed glass with vertical grooves and a narrower solid
  base, matching Aura's real tall ribbed glass references.
- Liquid: deep dark brown black coffee, transparent near the rim, glossy surface,
  realistic light reflections.
- Top surface: thin crema bubbles and a dark reflective coffee surface.
- Temperature cue: hot version with very subtle steam, or iced version with a few
  clear ice cubes and condensation if the drink variant is iced.

Scene:
- Light wooden cafe table.
- Soft daylight from a window.
- Blurred modern local cafe background with muted beige, olive, and grey tones.
- Optional subtle coffee beans on the table, but sparse and elegant. They must
  not dominate the frame.

Video sequence:
- 0.0-1.2 seconds: close preparation moment. A smooth dark coffee stream pours
  into the tall ribbed glass from a small glass server or pitcher. The liquid
  level rises naturally, with a thin crema forming at the surface. Do not show
  hands.
- 1.2-5.0 seconds: finished americano hero shot. The tall glass is centered and
  slowly rotates, or the camera slowly pushes in while the blurred background
  moves subtly.
- Coffee surface has gentle realistic movement. Reflections slide across the
  ribbed glass as it rotates.

Composition:
- Keep the tall glass fully visible and centered.
- Do not crop the rim or base.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean safe space at the top and bottom for frontend overlays.
- Make the drink readable both in full vertical detail view and horizontal menu
  card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, fingers, faces, extra cups, random logos, or third-party
  branding.
- No muddy coffee color, opaque black blob, distorted ribbed glass, warped rim,
  duplicate glass, messy spills, violent splashes, floating beans, or cartoon
  style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  liquid surface movement, reflections, rotation, or camera motion.
```

## Flat White Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium cafe product footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Flat White.
- Vessel: short clear ribbed glass or low ceramic cup, depending on the menu
  item reference. Prefer a short ribbed glass if no cup photo is provided.
- Liquid: smooth light caramel coffee, slightly lighter than cappuccino.
- The drink should never look like a mostly black americano or espresso for a
  long part of the clip. It should read as milk coffee almost immediately.
- Foam: thin velvety microfoam, flatter than cappuccino, with a simple white
  heart or tulip latte art.
- Hot-drink cue: nearly invisible thin steam, realistic and restrained.

Scene:
- Bright but soft cafe daylight.
- Light wooden table, clean premium surface.
- Blurred interior with grey sofa, cream wall, or muted olive detail.
- Calm editorial cafe mood, not dramatic or dark.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains a small espresso base partially
  mixed with milk, not a full dark black coffee. The visible liquid should be
  medium caramel brown from the start, not nearly black.
- 0.2-1.2 seconds: steamed milk pours gently into the coffee. The visible liquid
  must lighten continuously from medium caramel brown to warm creamy tan. The
  change must happen through realistic swirling and blending, with no one-frame
  jump from dark brown to white or pale tan.
- During the pour, the liquid level rises naturally, microfoam forms gradually,
  and the surface becomes smoother. The glass/cup shape and liquid volume must
  stay consistent from frame to frame.
- 1.2-5.0 seconds: finished flat white hero shot. The drink is now a stable warm
  creamy tan color with a thin microfoam layer and simple white heart or tulip
  latte art. The drink rotates slowly or the camera gently orbits, showing the
  glass/cup shape and the latte art.
- Foam should remain stable and realistic; only small surface movement. Do not
  change the drink color after the hero shot begins.

Composition:
- Keep the cup or glass centered and fully visible.
- Top latte art must remain visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave enough clean top and bottom space for the frontend.
- It must still work as a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No giant foam cap, no cappuccino-like thick foam, no distorted cup, no
  duplicate vessels, no messy spills, no cartoon style.
- No sudden color jump from dark espresso to creamy white. No magical liquid
  replacement, no instant transformation, no hard morph between preparation and
  finished drink in the same framing.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  microfoam settling, liquid ripples, steam, reflections, rotation, or camera
  motion.
```

## Эспрессо Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth minimal premium espresso footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Эспрессо.
- Vessel: small ceramic espresso cup or small clear espresso glass. The vessel
  should feel compact and premium, not like a large latte cup.
- Liquid: dark espresso, deep brown but not pure black, with realistic
  transparency at the thin edges.
- Top surface: rich golden-brown crema with tiny bubbles and glossy highlights.
- Hot-drink cue: very subtle steam, almost invisible and physically restrained.
- Scale: one small serving, centered and readable on mobile.

Scene:
- Modern Aura-style cafe table.
- Light wooden tabletop with warm daylight and soft ambient cafe lighting.
- Blurred background with muted olive, beige, grey, and cream tones.
- Optional subtle details: grey sofa blur, cream relief wall texture, small
  plant, or ribbed glass vase far in the background.
- Minimal composition with no clutter and no competing objects.

Video sequence:
- 0.0-1.0 seconds: close preparation moment. A narrow dark espresso stream pours
  into the small cup or glass. The liquid level rises naturally, and a golden
  crema layer forms gradually on the surface.
- The crema must appear through physical extraction and settling, not as a
  sudden flat color overlay. No instant switch from black liquid to finished
  crema.
- 1.0-5.0 seconds: finished espresso hero shot. The cup slowly rotates on the
  table or the camera slowly pushes in. Crema remains glossy with subtle tiny
  bubble movement and gentle reflections.

Composition:
- Keep the cup centered and fully visible.
- Do not make the cup too small; it should feel premium and readable on mobile.
- Main cup body stays mostly between 32% and 68% of frame height.
- Leave safe space at top and bottom for frontend overlays.
- It must still work as a menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No huge cup, no cappuccino foam, no latte art, no distorted cup, no messy
  spills, no excessive steam, no cartoon style.
- No sudden crema replacement, no liquid morph, no duplicate cup, no floating
  coffee stream.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  crema movement, steam, reflections, rotation, or camera motion.
```

## Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium cafe product footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Латте.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent
  base, matching Aura's real tall ribbed glass references. A low ceramic cup is
  acceptable only if the provided item reference uses ceramic.
- Liquid: warm creamy beige coffee, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee, with only subtle natural espresso ribbons
  during preparation. The finished drink should not have hard separated layers.
- Top surface: thin smooth microfoam with simple white heart or soft tulip latte
  art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden cafe table.
- Bright soft cafe daylight from a window, balanced with warm interior light.
- Blurred modern Aura-style background with muted olive, beige, grey, and cream
  tones.
- Optional subtle background details: grey sofa, cream relief wall texture,
  ribbed vase, small plant. Keep them out of focus and secondary.

Video sequence:
- 0.0-0.2 seconds: the glass already contains warm milk with a small espresso
  base beginning to mix, so the drink starts pale caramel rather than black.
- 0.2-1.2 seconds: a narrow espresso stream or steamed milk stream enters the
  glass and creates realistic caramel swirls. The color must evolve smoothly
  from pale caramel to a uniform creamy beige. No one-frame change, no sudden
  finished drink replacement.
- Microfoam forms gradually at the top; latte art should resolve naturally by
  the end of the pour, not pop into existence.
- 1.2-5.0 seconds: finished latte hero shot. The tall glass slowly rotates or
  the camera gently orbits/pushes in. The finished drink remains a stable creamy
  beige with thin microfoam and simple latte art.

Composition:
- Keep the full glass centered and readable.
- Rim, latte art, glass grooves, and base must remain visible.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The central band must still work as a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No sudden dark-to-white jump, no hard liquid replacement, no impossible
  layering, no distorted ribbed glass, no duplicate glass, no giant foam cap,
  no messy spills, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  microfoam settling, liquid swirls, reflections, rotation, or camera motion.
```

## Раф 300 Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium creamy coffee footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Раф 300.
- Vessel: 300 ml serving in a tall clear ribbed glass or a clean ceramic cup,
  matching the provided item reference if available. Prefer the tall ribbed
  glass when no specific vessel is provided.
- Liquid: uniform silky cream-coffee color, warm beige with a slight vanilla
  tone. It should look creamier than latte and smoother than cappuccino.
- Texture: velvety, lightly whipped, with a soft glossy microfoam surface.
- Top surface: smooth pale beige foam, optionally with very light vanilla sugar
  dust or a small cinnamon accent. Keep topping minimal.
- Hot-drink cue: thin realistic steam, not a visible cloud.

Scene:
- Light wooden cafe table with warm soft daylight.
- Cozy modern cafe background in muted olive, beige, grey, and cream tones.
- Optional blurred details: grey sofa, relief wall, window light, ribbed vase,
  small plant.
- Premium quiet cafe mood, not dessert-shop clutter.

Video sequence:
- 0.0-1.2 seconds: close preparation moment. A pale cream-and-coffee mixture is
  poured into the vessel in a smooth continuous stream. The liquid starts light
  caramel and becomes a uniform warm beige as it fills.
- The drink must not start as black espresso. It should read as creamy raf from
  the first frames. Color and texture change gradually through realistic
  blending, never by a single-frame morph.
- 1.2-5.0 seconds: finished Раф 300 hero shot. The vessel slowly rotates or the
  camera gently orbits. The surface is silky, with a soft microfoam sheen and
  subtle steam.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 24% and 72% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- It must still read as creamy raf when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No dark espresso phase, no abrupt beige transformation, no cappuccino-style
  thick foam cap, no latte art unless specifically requested, no distorted
  glass, no duplicate vessel, no whipped cream mountain, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  creamy surface movement, steam, reflections, rotation, or camera motion.
```

## Горячий бамбл Апельсин Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium hot citrus coffee footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Горячий бамбл Апельсин.
- Vessel: heat-safe clear glass, preferably tall ribbed glass or rounded clear
  glass from Aura's real glass references.
- Liquid: warm orange-citrus coffee drink. The base is translucent amber-orange,
  with espresso creating darker brown ribbons that blend into a warm
  orange-brown gradient.
- Layers: visible during preparation only. The finished drink may keep a soft
  amber-to-coffee gradient, but it should not look like hard separated stripes.
- Garnish: optional thin orange slice or small orange peel twist on the rim or
  table. Keep it subtle and realistic.
- Hot-drink cue: gentle steam. No ice, no condensation, no cold-drink styling.

Scene:
- Light wooden cafe table.
- Warm daylight with golden-orange highlights, still grounded in Aura's muted
  cafe palette.
- Blurred modern cafe background with cream, olive, grey, and beige tones.
- Optional sparse coffee beans or orange peel on the table, but they must not
  compete with the drink.

Video sequence:
- 0.0-0.3 seconds: the clear glass contains a warm translucent orange base,
  already glowing amber in the light.
- 0.3-1.3 seconds: a narrow espresso stream pours into the orange base. Dark
  coffee ribbons descend and curl naturally through the amber liquid, gradually
  forming a warm orange-brown gradient.
- The orange base must not suddenly turn black, and the espresso must not appear
  as an opaque block. Mixing must be continuous and physically believable.
- 1.3-5.0 seconds: finished hot orange bumble hero shot. The glass slowly rotates
  or the camera gently orbits. The drink remains warm amber-orange with darker
  coffee depth, subtle steam, and realistic glass reflections.

Composition:
- Keep the glass centered and fully visible.
- The amber-orange color must be readable on mobile.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink should still read as orange coffee in horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No ice cubes, no condensation, no cold cocktail look, no neon orange glow, no
  hard separated artificial layers, no instant color replacement, no distorted
  glass, no messy splash, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  citrus-coffee swirling, steam, reflections, rotation, or camera motion.
```

## Горячий бамбл Вишня Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium hot cherry coffee footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Горячий бамбл Вишня.
- Vessel: heat-safe clear glass, preferably tall ribbed glass or rounded clear
  glass from Aura's real glass references.
- Liquid: warm cherry coffee drink. The base is translucent deep cherry-red with
  ruby and amber highlights; espresso adds darker brown coffee ribbons.
- Layers: soft natural gradient during and after mixing, not hard synthetic
  stripes.
- Garnish: optional single cherry or small cherry accent near the glass, subtle
  and realistic. Do not make it a dessert cocktail.
- Hot-drink cue: gentle steam. No ice, no condensation, no cold-drink styling.

Scene:
- Light wooden cafe table.
- Warm cafe daylight with soft ruby reflections from the drink.
- Blurred Aura-style background in muted cream, beige, olive, and grey.
- Optional minimal coffee beans or cherry accent, kept small and secondary.

Video sequence:
- 0.0-0.3 seconds: the glass contains a warm translucent cherry base, deep ruby
  red but still believable and not neon.
- 0.3-1.3 seconds: a narrow espresso stream pours into the cherry base. Dark
  coffee ribbons mix gradually through the red liquid, creating a warm
  cherry-brown gradient with realistic swirling.
- The drink must not jump from red to brown or brown to red in one frame. Color
  changes must be continuous and physically driven by the pour.
- 1.3-5.0 seconds: finished hot cherry bumble hero shot. The glass slowly
  rotates or the camera gently orbits. The drink remains translucent ruby-brown
  with subtle steam and realistic reflections.

Composition:
- Keep the glass centered and fully visible.
- Ruby-red cherry color and coffee depth must stay readable on mobile.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The central crop must still read as a hot cherry coffee drink.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No ice cubes, no condensation, no cocktail umbrella, no neon red liquid, no
  fake syrup blob, no hard artificial layers, no instant color morph, no
  distorted glass, no messy splash, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  cherry-coffee swirling, steam, reflections, rotation, or camera motion.
```

## КАКАО Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth cozy premium cocoa footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: КАКАО.
- Vessel: warm ceramic cup or short clear ribbed glass, depending on the item
  reference. Prefer a cozy ceramic cup if no vessel photo is provided.
- Liquid: rich milk cocoa, warm medium chocolate-brown, creamy and opaque.
- Surface: smooth cocoa foam or very thin milk foam, with optional light cocoa
  dusting. No latte art unless specifically requested.
- Hot-drink cue: gentle realistic steam, soft and restrained.
- Texture: creamy and comforting, not watery and not black coffee.

Scene:
- Light wooden cafe table.
- Warm cozy daylight with soft beige and chocolate tones.
- Blurred Aura-style cafe background: cream wall, grey sofa, muted olive detail,
  or window light.
- Optional small cocoa powder accent on the table, minimal and clean.

Video sequence:
- 0.0-1.2 seconds: close preparation moment. Warm cocoa or steamed milk-chocolate
  mixture pours into the cup in a smooth continuous stream. The liquid remains
  consistently chocolate-brown, with slight natural lightening as foam forms.
- The cocoa should not turn black, white, or coffee-colored. Color changes must
  be subtle and continuous.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup slowly rotates or the
  camera gently pushes in. The surface shows soft foam, a slight cocoa dusting,
  and gentle steam.

Composition:
- Keep the cup centered and fully visible.
- Main cup body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- It must still look like cocoa in a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No marshmallow pile unless specifically requested, no whipped cream mountain,
  no coffee crema, no black espresso look, no sudden color jump, no distorted
  cup, no messy spill, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  cocoa foam settling, steam, reflections, rotation, or camera motion.
```

## Матча Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium matcha latte footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Матча Латте.
- Vessel: tall clear ribbed glass or rounded clear glass, matching Aura's real
  glass references. Ceramic cup is acceptable only if the item reference uses it.
- Liquid: creamy pale green matcha milk, natural muted green, not neon.
- Layers: during preparation, white milk and green matcha may swirl together.
  Finished drink should become a soft uniform matcha green or a very gentle
  milk-to-matcha gradient.
- Top surface: smooth pale green microfoam or light milk foam, optionally with a
  tiny dusting of matcha powder.
- Temperature cue: for hot matcha latte, subtle steam. No ice or condensation
  unless specifically generating an iced variant.

Scene:
- Light wooden cafe table.
- Soft daylight and clean calm cafe atmosphere.
- Muted cream, beige, olive, and grey background, with optional blurred plant or
  relief wall texture.
- Fresh but grounded color palette; matcha green should feel natural and
  appetizing.

Video sequence:
- 0.0-0.3 seconds: the glass contains warm milk or partially mixed pale matcha
  milk. The starting color should already be light creamy green or white with a
  small green matcha base, not empty.
- 0.3-1.3 seconds: green matcha concentrate or steamed milk pours in, creating
  soft green swirls through the milk. The color transitions gradually into a
  creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in
  one frame. Swirls and blending must be continuous and physically believable.
- 1.3-5.0 seconds: finished matcha latte hero shot. The drink slowly rotates or
  the camera gently orbits/pushes in. The finished color remains stable, soft
  matcha green, with realistic glass reflections and delicate foam.

Composition:
- Keep the full glass centered and readable.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The green drink must remain recognizable in a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No neon green liquid, no artificial glow, no hard synthetic layers, no sudden
  white-to-green color jump, no distorted glass, no duplicate vessel, no messy
  powder cloud, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  matcha swirls, foam settling, steam, reflections, rotation, or camera motion.
```

## Айс Капучино Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium iced coffee footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Айс Капучино.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent
  base, matching Aura's real tall ribbed glass references.
- Liquid: chilled espresso and milk, creamy caramel-brown, darker than iced
  latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap, thicker than iced latte foam but still
  smooth and realistic. The foam should sit on top, not become a whipped cream
  mountain.
- Temperature cue: cold condensation droplets on the outside of the glass. No
  steam.

Scene:
- Light wooden cafe table.
- Bright natural window light with a fresh cold-drink mood.
- Blurred Aura-style background in muted olive, beige, grey, and cream tones.
- Optional subtle plant, window, grey sofa, or ribbed vase in the background.
  Keep all background details soft and secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled
  milk coffee, light caramel-brown rather than black.
- 0.3-1.2 seconds: chilled espresso or milk pours over the ice. The liquid level
  rises naturally, ice shifts slightly, and the coffee color changes through
  realistic swirling from medium caramel to creamy caramel-brown.
- Cold foam forms or is poured on top gradually. It must not appear instantly in
  one frame, and the drink must not jump from dark espresso to pale milk.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates
  or the camera gently orbits/pushes in. Condensation catches the light, ice
  remains visible, and the cold foam cap stays stable.

Composition:
- Keep the full glass centered and fully visible.
- Ice, foam cap, condensation, glass grooves, rim, and base must remain readable.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read as iced cappuccino in a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No steam, no hot-drink styling, no giant whipped cream, no sudden dark-to-pale
  color jump, no instant foam cap, no floating ice, no distorted ribbed glass,
  no duplicate glass, no messy splash, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  ice movement, foam settling, condensation highlights, rotation, or camera
  motion.
```

## Айс Американо Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth minimal premium iced americano footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Айс Американо.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent
  base, matching Aura's real tall ribbed glass references.
- Liquid: chilled black coffee, deep transparent brown with amber highlights,
  not opaque black.
- Ice: clear realistic ice cubes, visible through the coffee and glass grooves.
- Top surface: glossy cold coffee surface with a few tiny crema bubbles near the
  pour.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden cafe table.
- Bright natural daylight, clean and refreshing.
- Blurred modern cafe background with muted beige, olive, grey, and cream tones.
- Optional sparse coffee beans or a small plant in the background, out of focus
  and not competing with the drink.

Video sequence:
- 0.0-0.3 seconds: the glass already contains clear ice cubes and a small amount
  of cold water or light coffee tint. The glass must not be empty.
- 0.3-1.2 seconds: dark espresso or coffee pours over the ice. The liquid flows
  down between the cubes, creating transparent amber-brown ribbons that darken
  the drink gradually.
- The drink should remain transparent and cold. Do not make it a solid black
  block, and do not let the ice vanish or change shape.
- 1.2-5.0 seconds: finished iced americano hero shot. The glass slowly rotates
  or the camera gently pushes in. Ice glints through the coffee, condensation
  catches light, and the surface remains glossy with subtle movement.

Composition:
- Keep the full glass centered and fully visible.
- Ice, rim, base, dark coffee color, and condensation must remain readable.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- It must still look like iced americano in a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No steam, no hot coffee cup, no milk, no foam cap, no opaque black blob, no
  disappearing ice, no floating ice outside the glass, no distorted ribbed
  glass, no duplicate glass, no messy splash, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  ice movement, coffee surface ripples, condensation highlights, rotation, or
  camera motion.
```

## Айс Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium iced latte footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Айс Латте.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent
  base, matching Aura's real tall ribbed glass references.
- Liquid: chilled milk and espresso, creamy beige with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Layers: gentle espresso ribbons during preparation. Finished drink becomes
  creamy beige with subtle natural marbling, not hard separated stripes.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the outside of the glass. No steam.

Scene:
- Light wooden cafe table.
- Bright natural window light and calm modern cafe atmosphere.
- Blurred Aura-style background with muted cream, beige, olive, and grey tones.
- Optional subtle grey sofa, relief wall, plant, or ribbed vase in the blur.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled milk. The base is
  pale milk-white with realistic ice refraction.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel-brown
  ribbons that descend and blend gradually into a creamy beige iced latte.
- The color must evolve continuously through swirling. No sudden jump from white
  milk to beige coffee, no hard cut to a finished drink, and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or
  the camera gently orbits/pushes in. Ice remains visible, condensation catches
  light, and the liquid settles into creamy beige with subtle marbling.

Composition:
- Keep the full glass centered and readable.
- Ice, condensation, rim, base, and creamy beige coffee color must remain
  visible.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The central crop must still read as iced latte in a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No steam, no hot-drink styling, no sudden white-to-brown jump, no hard liquid
  replacement, no floating ice, no dirty grey liquid, no distorted ribbed glass,
  no duplicate glass, no messy splash, no cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  ice movement, liquid marbling, condensation highlights, rotation, or camera
  motion.
```

## Айс Матча латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a
modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds.
- Smooth premium iced matcha latte footage.
- Mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons,
  no watermark.

Drink:
- Name: Айс Матча латте.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent
  base, matching Aura's real tall ribbed glass references.
- Liquid: chilled milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Layers: during preparation, white milk and green matcha swirl together. The
  finished drink may keep a soft milk-to-matcha gradient or become uniform pale
  green, but it must not have hard synthetic layers.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the outside of the glass. No steam.

Scene:
- Light wooden cafe table.
- Bright natural daylight with a fresh calm cafe mood.
- Muted cream, beige, olive, and grey background with optional blurred plant or
  relief wall texture.
- Matcha green should look natural, creamy, and appetizing.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled milk or partially
  mixed pale matcha milk. The starting color should be white with a soft green
  tint, not empty and not neon.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and milk,
  creating soft green ribbons that swirl and blend gradually into creamy pale
  matcha green.
- The liquid must not jump from white to bright green or from green to white in
  one frame. Ice must remain visible and physically consistent while the drink
  blends.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly
  rotates or the camera gently orbits/pushes in. Condensation catches light, ice
  remains visible, and the finished color stays stable soft matcha green.

Composition:
- Keep the full glass centered and readable.
- Ice, condensation, glass grooves, rim, base, and green drink color must remain
  visible.
- Main glass body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The green drink must remain recognizable in a horizontal menu-card crop.

Negative prompt:
- No UI, text, price, nutrition labels, icons, or status bar.
- No people, hands, faces, extra cups, random logos, or third-party branding.
- No steam, no hot-drink styling, no neon green liquid, no artificial glow, no
  sudden white-to-green color jump, no hard synthetic layers, no disappearing
  ice, no distorted ribbed glass, no duplicate glass, no messy powder cloud, no
  cartoon style.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into
  settling liquid, foam/ice/steam/reflections continue moving, and hero rotation
  or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look
  like a minute passed between frames.
- No abrupt freeze after the pour, no still-frame hero shot, no sudden stop of
  ice movement, matcha swirls, condensation highlights, rotation, or camera
  motion.
```

## Full Menu Exact Prompt Catalog

This section intentionally duplicates structure for every menu drink. Each block is copy-ready and self-contained. Do not replace these with family abstractions. Every prompt keeps the same Aura Coffee mobile-first constraints: exact Cyrillic `Name:`, no baked-in app UI, no sudden color morph, no time-skip from active pouring to a completed drink, and one smooth continuous drink lifecycle from preparation through hero motion.

### АПЕЛЬСИНОВЫЙ ФРЕШ Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: АПЕЛЬСИНОВЫЙ ФРЕШ.
- Vessel: tall clear glass or rounded clear glass.
- Liquid: freshly squeezed orange fresh juice, bright natural orange with realistic pulp and slight translucency, natural and appetizing.
- Texture: realistic juice body with subtle pulp, tiny bubbles, and natural translucency.
- Temperature cue: lightly chilled freshness; optional faint condensation only if served cold.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: orange fresh juice pours into the clear glass in a smooth continuous stream. Pulp and bubbles move naturally as the level rises.
- The color remains natural and consistent; no neon color and no instant frozen surface.
- 1.2-5.0 seconds: finished fresh juice hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, pulp movement, bubbles, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No soda carbonation, no cocktail styling, no artificial fruit chunks, no neon orange.
```

### Айс Американо Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Американо.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled black coffee, deep transparent brown with amber highlights, not opaque black.
- Ice: clear realistic ice cubes visible through the coffee.
- Surface: glossy cold coffee surface with tiny crema bubbles near the pour.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains clear ice cubes and a small amount of cold water or light coffee tint.
- 0.3-1.2 seconds: dark espresso or coffee pours over the ice, creating transparent amber-brown ribbons that darken the drink gradually.
- The drink remains transparent and cold; ice must not vanish or change shape.
- 1.2-5.0 seconds: finished iced americano hero shot. The glass slowly rotates or the camera gently pushes in. Ice glints, condensation, surface ripples, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No milk, no foam cap, no opaque black blob.
```

### Айс Капучино Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Капучино.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and classic dairy milk, creamy beige, darker than iced latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap made with classic dairy milk; thicker than iced latte foam, smooth and realistic.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled classic dairy milk coffee.
- 0.3-1.2 seconds: chilled espresso and classic dairy milk pour over the ice. The liquid level rises naturally, ice shifts slightly, and the coffee color changes through realistic swirling into creamy beige.
- Cold foam forms gradually on top; it must not appear instantly in one frame.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates or the camera gently orbits. Condensation, foam settling, ice glints, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No giant whipped cream, no sudden dark-to-pale jump, no instant foam cap.
```

### Айс Капучино на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Капучино на банановом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and banana milk, warm creamy beige with a subtle banana tint, darker than iced latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap made with banana milk; thicker than iced latte foam, smooth and realistic.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled banana milk coffee.
- 0.3-1.2 seconds: chilled espresso and banana milk pour over the ice. The liquid level rises naturally, ice shifts slightly, and the coffee color changes through realistic swirling into warm creamy beige with a subtle banana tint.
- Cold foam forms gradually on top; it must not appear instantly in one frame.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates or the camera gently orbits. Condensation, foam settling, ice glints, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No giant whipped cream, no sudden dark-to-pale jump, no instant foam cap.
```

### Айс Капучино на безлактозном Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Капучино на безлактозном.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and lactose-free milk, neutral creamy beige, close to classic milk, darker than iced latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap made with lactose-free milk; thicker than iced latte foam, smooth and realistic.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled lactose-free milk coffee.
- 0.3-1.2 seconds: chilled espresso and lactose-free milk pour over the ice. The liquid level rises naturally, ice shifts slightly, and the coffee color changes through realistic swirling into neutral creamy beige, close to classic milk.
- Cold foam forms gradually on top; it must not appear instantly in one frame.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates or the camera gently orbits. Condensation, foam settling, ice glints, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No giant whipped cream, no sudden dark-to-pale jump, no instant foam cap.
```

### Айс Капучино на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Капучино на кокосовом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and coconut milk, slightly brighter white-cream beige, darker than iced latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap made with coconut milk; thicker than iced latte foam, smooth and realistic.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled coconut milk coffee.
- 0.3-1.2 seconds: chilled espresso and coconut milk pour over the ice. The liquid level rises naturally, ice shifts slightly, and the coffee color changes through realistic swirling into slightly brighter white-cream beige.
- Cold foam forms gradually on top; it must not appear instantly in one frame.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates or the camera gently orbits. Condensation, foam settling, ice glints, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No giant whipped cream, no sudden dark-to-pale jump, no instant foam cap.
```

### Айс Капучино на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Капучино на миндальном молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and almond milk, slightly nutty beige, darker than iced latte but not black.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Foam: cold cappuccino-style foam cap made with almond milk; thicker than iced latte foam, smooth and realistic.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled almond milk coffee.
- 0.3-1.2 seconds: chilled espresso and almond milk pour over the ice. The liquid level rises naturally, ice shifts slightly, and the coffee color changes through realistic swirling into slightly nutty beige.
- Cold foam forms gradually on top; it must not appear instantly in one frame.
- 1.2-5.0 seconds: finished iced cappuccino hero shot. The glass slowly rotates or the camera gently orbits. Condensation, foam settling, ice glints, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No giant whipped cream, no sudden dark-to-pale jump, no instant foam cap.
```

### Айс Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Латте.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled classic dairy milk and espresso, creamy beige with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled classic dairy milk.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel ribbons that descend and blend gradually into creamy beige.
- The color must evolve continuously through swirling; no sudden white-to-brown jump and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, liquid marbling, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hard separated stripes, no dirty grey liquid, no instant finished drink.
```

### Айс Латте на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Латте на банановом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled banana milk and espresso, warm creamy beige with a subtle banana tint with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled banana milk.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel ribbons that descend and blend gradually into warm creamy beige with a subtle banana tint.
- The color must evolve continuously through swirling; no sudden white-to-brown jump and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, liquid marbling, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hard separated stripes, no dirty grey liquid, no instant finished drink.
```

### Айс Латте на безлактозном Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Латте на безлактозном.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled lactose-free milk and espresso, neutral creamy beige, close to classic milk with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled lactose-free milk.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel ribbons that descend and blend gradually into neutral creamy beige, close to classic milk.
- The color must evolve continuously through swirling; no sudden white-to-brown jump and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, liquid marbling, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hard separated stripes, no dirty grey liquid, no instant finished drink.
```

### Айс Латте на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Латте на кокосовом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled coconut milk and espresso, slightly brighter white-cream beige with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled coconut milk.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel ribbons that descend and blend gradually into slightly brighter white-cream beige.
- The color must evolve continuously through swirling; no sudden white-to-brown jump and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, liquid marbling, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hard separated stripes, no dirty grey liquid, no instant finished drink.
```

### Айс Латте на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Латте на миндальном молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled almond milk and espresso, slightly nutty beige with soft caramel marbling.
- Ice: several clear realistic ice cubes visible through the ribbed glass.
- Surface: cold glossy surface with light microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled almond milk.
- 0.3-1.2 seconds: espresso pours over the milk and ice, creating caramel ribbons that descend and blend gradually into slightly nutty beige.
- The color must evolve continuously through swirling; no sudden white-to-brown jump and no disappearing ice.
- 1.2-5.0 seconds: finished iced latte hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, liquid marbling, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hard separated stripes, no dirty grey liquid, no instant finished drink.
```

### Айс Матча Латте на безлактозном Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча Латте на безлактозном.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled lactose-free milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled lactose-free milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and lactose-free milk, creating soft green ribbons that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green; ice must remain visible and physically consistent.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly rotates or the camera gently orbits. Condensation, ice, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No neon green liquid, no hard synthetic layers, no disappearing ice.
```

### Айс Матча латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча латте.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled classic dairy milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled classic dairy milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and classic dairy milk, creating soft green ribbons that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green; ice must remain visible and physically consistent.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly rotates or the camera gently orbits. Condensation, ice, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No neon green liquid, no hard synthetic layers, no disappearing ice.
```

### Айс Матча латте на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча латте на банановом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled banana milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled banana milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and banana milk, creating soft green ribbons that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green; ice must remain visible and physically consistent.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly rotates or the camera gently orbits. Condensation, ice, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No neon green liquid, no hard synthetic layers, no disappearing ice.
```

### Айс Матча латте на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча латте на кокосовом молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled coconut milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled coconut milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and coconut milk, creating soft green ribbons that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green; ice must remain visible and physically consistent.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly rotates or the camera gently orbits. Condensation, ice, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No neon green liquid, no hard synthetic layers, no disappearing ice.
```

### Айс Матча латте на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча латте на миндальном молоке.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled almond milk and matcha, creamy pale natural green, not neon.
- Ice: several clear realistic ice cubes visible through the matcha milk.
- Surface: cold glossy surface with light pale-green foam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and chilled almond milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and almond milk, creating soft green ribbons that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green; ice must remain visible and physically consistent.
- 1.3-5.0 seconds: finished iced matcha latte hero shot. The glass slowly rotates or the camera gently orbits. Condensation, ice, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No neon green liquid, no hard synthetic layers, no disappearing ice.
```

### Айс Матча тоник Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Матча тоник.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: sparkling tonic and matcha, transparent pale green-gold, natural and not neon.
- Ice: several clear realistic ice cubes visible through the tonic.
- Surface: active fine carbonation bubbles, glossy cold surface.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and sparkling tonic with visible bubbles.
- 0.3-1.3 seconds: green matcha concentrate pours over the ice and tonic, forming natural green ribbons through clear fizz.
- The matcha blends gradually while carbonation keeps rising; no sudden green flash and no disappearing bubbles.
- 1.3-5.0 seconds: finished iced matcha tonic hero shot. The glass slowly rotates or the camera gently orbits. Bubbles, ice, condensation, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No milk, no neon green, no powder cloud, no flat non-carbonated tonic.
```

### Айс Раф Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Раф.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled cream-coffee mixture, silky warm beige with a slight vanilla tone.
- Ice: several clear realistic ice cubes visible through the glass.
- Surface: cold glossy microfoam, smooth and creamy.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of chilled cream-coffee mixture.
- 0.3-1.2 seconds: pale cream-and-coffee mixture pours over the ice, filling the glass smoothly while ice shifts slightly.
- The drink must read as creamy raf from the first frames; no black espresso phase and no abrupt beige transformation.
- 1.2-5.0 seconds: finished iced raf hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, creamy surface movement, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No whipped cream mountain, no cappuccino foam cap, no latte art unless requested.
```

### Айс Флэт Уайт Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Айс Флэт Уайт.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: chilled espresso and milk, compact creamy tan, stronger-looking than iced latte but not black.
- Ice: clear realistic ice cubes visible through the glass.
- Surface: thin cold microfoam or tiny bubbles.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and a small amount of partially mixed chilled milk coffee, medium caramel rather than black.
- 0.3-1.2 seconds: chilled milk or espresso pours in and lightens continuously into compact creamy tan through realistic swirling.
- No one-frame color jump from dark espresso to pale milk; ice remains visible and consistent.
- 1.2-5.0 seconds: finished iced flat white hero shot. The glass slowly rotates or the camera gently orbits. Ice, microfoam, condensation, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No latte-sized milkiness, no giant foam cap, no sudden dark-to-white jump.
```

### Американо Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Американо.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot black coffee, deep transparent brown with amber highlights, not pure black.
- Surface: glossy coffee surface with a thin crema ring and tiny bubbles.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: dark coffee pours into the vessel. The liquid level rises naturally and a thin crema ring forms gradually.
- The coffee surface keeps gentle movement and realistic reflections.
- 1.2-5.0 seconds: finished americano hero shot. The vessel slowly rotates or the camera gently pushes in. Steam, surface ripples, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No milk, no foam cap, no opaque black blob.
```

### Бамбл фрэш Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Бамбл фрэш.
- Vessel: heat-safe clear glass or tall ribbed glass.
- Liquid: orange fresh bumble coffee, bright orange fresh base with darker espresso ribbons.
- Layers: natural gradient during preparation; finished drink keeps soft citrus/berry-to-coffee depth without hard stripes.
- Temperature cue: ice and condensation, no steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass contains ice and chilled orange fresh base.
- 0.3-1.3 seconds: espresso pours over the ice into the base. Coffee ribbons blend gradually while ice shifts slightly.
- Mixing is continuous; no sudden dark block, no disappearing ice, no instant finished drink.
- 1.3-5.0 seconds: finished cold bumble hero shot. The glass slowly rotates or the camera gently orbits. Ice, condensation, swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No hot-drink styling, no hard artificial layers, no neon syrup.
```

### Горячий бамбл Апельсин Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Горячий бамбл Апельсин.
- Vessel: heat-safe clear glass or tall ribbed glass.
- Liquid: orange-citrus bumble coffee, warm translucent amber-orange base with darker espresso ribbons.
- Layers: natural gradient during preparation; finished drink keeps soft citrus/berry-to-coffee depth without hard stripes.
- Temperature cue: gentle steam, no ice, no condensation-heavy cold styling.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass contains a warm orange-citrus base, already glowing naturally in the light.
- 0.3-1.3 seconds: espresso pours into the base. Dark coffee ribbons descend and curl gradually through the liquid.
- Mixing is continuous and physically believable; no sudden black block or instant color replacement.
- 1.3-5.0 seconds: finished hot bumble hero shot. The glass slowly rotates or the camera gently orbits. Swirls, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No cold cocktail look, no hard artificial layers, no neon syrup.
```

### Горячий бамбл Вишня Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Горячий бамбл Вишня.
- Vessel: heat-safe clear glass or tall ribbed glass.
- Liquid: cherry bumble coffee, warm translucent ruby-red base with darker espresso ribbons.
- Layers: natural gradient during preparation; finished drink keeps soft citrus/berry-to-coffee depth without hard stripes.
- Temperature cue: gentle steam, no ice, no condensation-heavy cold styling.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass contains a warm cherry base, already glowing naturally in the light.
- 0.3-1.3 seconds: espresso pours into the base. Dark coffee ribbons descend and curl gradually through the liquid.
- Mixing is continuous and physically believable; no sudden black block or instant color replacement.
- 1.3-5.0 seconds: finished hot bumble hero shot. The glass slowly rotates or the camera gently orbits. Swirls, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No cold cocktail look, no hard artificial layers, no neon syrup.
```

### КАКАО Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: КАКАО.
- Vessel: cozy ceramic cup or short clear ribbed glass, matching the provided item reference if available.
- Liquid: rich milk cocoa made with classic dairy milk, warm medium chocolate-brown, creamy and opaque.
- Surface: smooth cocoa foam or thin milk foam, optionally with light cocoa dusting.
- Hot-drink cue: gentle realistic steam, soft and restrained.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: warm cocoa mixture with classic dairy milk pours into the vessel in a smooth continuous stream.
- The liquid remains consistently chocolate-brown, with only subtle natural lightening as foam forms.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup or glass slowly rotates or the camera gently pushes in. Cocoa foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No coffee crema, no black espresso look, no marshmallow pile unless requested.
```

### КАКАО на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: КАКАО на банановом молоке.
- Vessel: cozy ceramic cup or short clear ribbed glass, matching the provided item reference if available.
- Liquid: rich milk cocoa made with banana milk, warm medium chocolate-brown with banana milk creaminess, creamy and opaque.
- Surface: smooth cocoa foam or thin milk foam, optionally with light cocoa dusting.
- Hot-drink cue: gentle realistic steam, soft and restrained.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: warm cocoa mixture with banana milk pours into the vessel in a smooth continuous stream.
- The liquid remains consistently chocolate-brown, with only subtle natural lightening as foam forms.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup or glass slowly rotates or the camera gently pushes in. Cocoa foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No coffee crema, no black espresso look, no marshmallow pile unless requested.
```

### КАКАО на безлактозном Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: КАКАО на безлактозном.
- Vessel: cozy ceramic cup or short clear ribbed glass, matching the provided item reference if available.
- Liquid: rich milk cocoa made with lactose-free milk, warm medium chocolate-brown with lactose-free milk creaminess, creamy and opaque.
- Surface: smooth cocoa foam or thin milk foam, optionally with light cocoa dusting.
- Hot-drink cue: gentle realistic steam, soft and restrained.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: warm cocoa mixture with lactose-free milk pours into the vessel in a smooth continuous stream.
- The liquid remains consistently chocolate-brown, with only subtle natural lightening as foam forms.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup or glass slowly rotates or the camera gently pushes in. Cocoa foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No coffee crema, no black espresso look, no marshmallow pile unless requested.
```

### КАКАО на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: КАКАО на кокосовом молоке.
- Vessel: cozy ceramic cup or short clear ribbed glass, matching the provided item reference if available.
- Liquid: rich milk cocoa made with coconut milk, warm medium chocolate-brown with coconut milk creaminess, creamy and opaque.
- Surface: smooth cocoa foam or thin milk foam, optionally with light cocoa dusting.
- Hot-drink cue: gentle realistic steam, soft and restrained.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: warm cocoa mixture with coconut milk pours into the vessel in a smooth continuous stream.
- The liquid remains consistently chocolate-brown, with only subtle natural lightening as foam forms.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup or glass slowly rotates or the camera gently pushes in. Cocoa foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No coffee crema, no black espresso look, no marshmallow pile unless requested.
```

### КАКАО на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: КАКАО на миндальном молоке.
- Vessel: cozy ceramic cup or short clear ribbed glass, matching the provided item reference if available.
- Liquid: rich milk cocoa made with almond milk, warm medium chocolate-brown with almond milk creaminess, creamy and opaque.
- Surface: smooth cocoa foam or thin milk foam, optionally with light cocoa dusting.
- Hot-drink cue: gentle realistic steam, soft and restrained.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: warm cocoa mixture with almond milk pours into the vessel in a smooth continuous stream.
- The liquid remains consistently chocolate-brown, with only subtle natural lightening as foam forms.
- 1.2-5.0 seconds: finished cocoa hero shot. The cup or glass slowly rotates or the camera gently pushes in. Cocoa foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No coffee crema, no black espresso look, no marshmallow pile unless requested.
```

### Капучино Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Капучино.
- Vessel: short clear ribbed glass or ceramic cappuccino cup, matching the provided item reference if available.
- Liquid: hot espresso and classic dairy milk, creamy beige, warm and creamy.
- Foam: dense cappuccino foam made with classic dairy milk, smooth and realistic.
- Top surface: simple white heart or tulip latte art, centered and not too complex.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: steamed classic dairy milk pours into espresso, forming creamy swirls and gradually building foam.
- The drink must evolve continuously; no dark espresso phase suddenly turning pale.
- 1.2-5.0 seconds: finished cappuccino hero shot. The cup or glass slowly rotates or the camera gently orbits. Foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no instant latte art, no cappuccino-to-latte morph.
```

### Капучино на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Капучино на банановом молоке.
- Vessel: short clear ribbed glass or ceramic cappuccino cup, matching the provided item reference if available.
- Liquid: hot espresso and banana milk, warm creamy beige with a subtle banana tint, warm and creamy.
- Foam: dense cappuccino foam made with banana milk, smooth and realistic.
- Top surface: simple white heart or tulip latte art, centered and not too complex.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: steamed banana milk pours into espresso, forming creamy swirls and gradually building foam.
- The drink must evolve continuously; no dark espresso phase suddenly turning pale.
- 1.2-5.0 seconds: finished cappuccino hero shot. The cup or glass slowly rotates or the camera gently orbits. Foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no instant latte art, no cappuccino-to-latte morph.
```

### Капучино на безлактозном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Капучино на безлактозном молоке.
- Vessel: short clear ribbed glass or ceramic cappuccino cup, matching the provided item reference if available.
- Liquid: hot espresso and lactose-free milk, neutral creamy beige, close to classic milk, warm and creamy.
- Foam: dense cappuccino foam made with lactose-free milk, smooth and realistic.
- Top surface: simple white heart or tulip latte art, centered and not too complex.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: steamed lactose-free milk pours into espresso, forming creamy swirls and gradually building foam.
- The drink must evolve continuously; no dark espresso phase suddenly turning pale.
- 1.2-5.0 seconds: finished cappuccino hero shot. The cup or glass slowly rotates or the camera gently orbits. Foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no instant latte art, no cappuccino-to-latte morph.
```

### Капучино на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Капучино на кокосовом молоке.
- Vessel: short clear ribbed glass or ceramic cappuccino cup, matching the provided item reference if available.
- Liquid: hot espresso and coconut milk, slightly brighter white-cream beige, warm and creamy.
- Foam: dense cappuccino foam made with coconut milk, smooth and realistic.
- Top surface: simple white heart or tulip latte art, centered and not too complex.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: steamed coconut milk pours into espresso, forming creamy swirls and gradually building foam.
- The drink must evolve continuously; no dark espresso phase suddenly turning pale.
- 1.2-5.0 seconds: finished cappuccino hero shot. The cup or glass slowly rotates or the camera gently orbits. Foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no instant latte art, no cappuccino-to-latte morph.
```

### Капучино на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Капучино на миндальном молоке.
- Vessel: short clear ribbed glass or ceramic cappuccino cup, matching the provided item reference if available.
- Liquid: hot espresso and almond milk, slightly nutty beige, warm and creamy.
- Foam: dense cappuccino foam made with almond milk, smooth and realistic.
- Top surface: simple white heart or tulip latte art, centered and not too complex.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: steamed almond milk pours into espresso, forming creamy swirls and gradually building foam.
- The drink must evolve continuously; no dark espresso phase suddenly turning pale.
- 1.2-5.0 seconds: finished cappuccino hero shot. The cup or glass slowly rotates or the camera gently orbits. Foam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no instant latte art, no cappuccino-to-latte morph.
```

### Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Латте.
- Vessel: tall clear ribbed glass or ceramic latte cup, matching the provided item reference if available.
- Liquid: hot espresso and classic dairy milk, creamy beige, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee; only subtle espresso ribbons during preparation.
- Top surface: thin smooth microfoam with simple white heart or tulip latte art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains warm classic dairy milk with a small espresso base beginning to mix.
- 0.2-1.2 seconds: espresso or steamed classic dairy milk enters the vessel and creates realistic caramel swirls. The color evolves smoothly into creamy beige.
- Microfoam and simple latte art resolve gradually, never popping into existence.
- 1.2-5.0 seconds: finished latte hero shot. The vessel slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no hard layers, no instant latte art.
```

### Латте на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Латте на банановом молоке.
- Vessel: tall clear ribbed glass or ceramic latte cup, matching the provided item reference if available.
- Liquid: hot espresso and banana milk, warm creamy beige with a subtle banana tint, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee; only subtle espresso ribbons during preparation.
- Top surface: thin smooth microfoam with simple white heart or tulip latte art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains warm banana milk with a small espresso base beginning to mix.
- 0.2-1.2 seconds: espresso or steamed banana milk enters the vessel and creates realistic caramel swirls. The color evolves smoothly into warm creamy beige with a subtle banana tint.
- Microfoam and simple latte art resolve gradually, never popping into existence.
- 1.2-5.0 seconds: finished latte hero shot. The vessel slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no hard layers, no instant latte art.
```

### Латте на безлактозном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Латте на безлактозном молоке.
- Vessel: tall clear ribbed glass or ceramic latte cup, matching the provided item reference if available.
- Liquid: hot espresso and lactose-free milk, neutral creamy beige, close to classic milk, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee; only subtle espresso ribbons during preparation.
- Top surface: thin smooth microfoam with simple white heart or tulip latte art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains warm lactose-free milk with a small espresso base beginning to mix.
- 0.2-1.2 seconds: espresso or steamed lactose-free milk enters the vessel and creates realistic caramel swirls. The color evolves smoothly into neutral creamy beige, close to classic milk.
- Microfoam and simple latte art resolve gradually, never popping into existence.
- 1.2-5.0 seconds: finished latte hero shot. The vessel slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no hard layers, no instant latte art.
```

### Латте на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Латте на кокосовом молоке.
- Vessel: tall clear ribbed glass or ceramic latte cup, matching the provided item reference if available.
- Liquid: hot espresso and coconut milk, slightly brighter white-cream beige, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee; only subtle espresso ribbons during preparation.
- Top surface: thin smooth microfoam with simple white heart or tulip latte art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains warm coconut milk with a small espresso base beginning to mix.
- 0.2-1.2 seconds: espresso or steamed coconut milk enters the vessel and creates realistic caramel swirls. The color evolves smoothly into slightly brighter white-cream beige.
- Microfoam and simple latte art resolve gradually, never popping into existence.
- 1.2-5.0 seconds: finished latte hero shot. The vessel slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no hard layers, no instant latte art.
```

### Латте на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Латте на миндальном молоке.
- Vessel: tall clear ribbed glass or ceramic latte cup, matching the provided item reference if available.
- Liquid: hot espresso and almond milk, slightly nutty beige, lighter and milkier than cappuccino.
- Layers: mostly uniform milk coffee; only subtle espresso ribbons during preparation.
- Top surface: thin smooth microfoam with simple white heart or tulip latte art.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains warm almond milk with a small espresso base beginning to mix.
- 0.2-1.2 seconds: espresso or steamed almond milk enters the vessel and creates realistic caramel swirls. The color evolves smoothly into slightly nutty beige.
- Microfoam and simple latte art resolve gradually, never popping into existence.
- 1.2-5.0 seconds: finished latte hero shot. The vessel slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No giant foam cap, no hard layers, no instant latte art.
```

### Лимонад Грейпфрут Бузина Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Лимонад Грейпфрут Бузина.
- Vessel: tall clear glass with ice.
- Liquid: sparkling lemonade, pale pink grapefruit with elderflower brightness, refreshing and natural.
- Garnish: thin grapefruit slice or tiny elderflower accent, subtle and realistic.
- Surface: fine carbonation bubbles and glossy cold surface.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: grapefruit-elderflower lemonade pours over ice. Bubbles rise continuously and the liquid level rises naturally.
- Fruit color and garnish remain physically consistent; no neon color, no instant stillness.
- 1.2-5.0 seconds: finished lemonade hero shot. The glass slowly rotates or the camera gently orbits. Bubbles, ice, condensation, garnish, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No cocktail umbrella, no artificial glow, no syrup blob, no floating garnish outside the glass.
```

### Лимонад Клубника-Мохито Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Лимонад Клубника-Мохито.
- Vessel: tall clear glass with ice.
- Liquid: sparkling lemonade, soft red strawberry lemonade with mint-green accents, refreshing and natural.
- Garnish: small mint leaf and subtle strawberry accent, subtle and realistic.
- Surface: fine carbonation bubbles and glossy cold surface.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: strawberry-mint lemonade pours over ice. Bubbles rise continuously and the liquid level rises naturally.
- Fruit color and garnish remain physically consistent; no neon color, no instant stillness.
- 1.2-5.0 seconds: finished lemonade hero shot. The glass slowly rotates or the camera gently orbits. Bubbles, ice, condensation, garnish, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No cocktail umbrella, no artificial glow, no syrup blob, no floating garnish outside the glass.
```

### Лимонад Манго-Маракуйя Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Лимонад Манго-Маракуйя.
- Vessel: tall clear glass with ice.
- Liquid: sparkling lemonade, golden mango-passionfruit, lightly opaque but refreshing, refreshing and natural.
- Garnish: small passionfruit or mango accent, subtle and realistic.
- Surface: fine carbonation bubbles and glossy cold surface.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: mango-passionfruit lemonade pours over ice. Bubbles rise continuously and the liquid level rises naturally.
- Fruit color and garnish remain physically consistent; no neon color, no instant stillness.
- 1.2-5.0 seconds: finished lemonade hero shot. The glass slowly rotates or the camera gently orbits. Bubbles, ice, condensation, garnish, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No cocktail umbrella, no artificial glow, no syrup blob, no floating garnish outside the glass.
```

### Матча Латте Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Матча Латте.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot classic dairy milk and matcha, creamy pale natural green, not neon.
- Layers: soft matcha swirls during preparation; finished drink is uniform pale green or a gentle milk-to-matcha gradient.
- Top surface: smooth pale-green microfoam, optionally with tiny matcha dusting.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the vessel already contains warm classic dairy milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate or steamed classic dairy milk pours in, creating soft green swirls that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in one frame.
- 1.3-5.0 seconds: finished matcha latte hero shot. The vessel slowly rotates or the camera gently orbits. Foam settling, steam, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No neon green liquid, no hard synthetic layers, no powder cloud.
```

### Матча Латте на банановом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Матча Латте на банановом молоке.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot banana milk and matcha, creamy pale natural green, not neon.
- Layers: soft matcha swirls during preparation; finished drink is uniform pale green or a gentle milk-to-matcha gradient.
- Top surface: smooth pale-green microfoam, optionally with tiny matcha dusting.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the vessel already contains warm banana milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate or steamed banana milk pours in, creating soft green swirls that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in one frame.
- 1.3-5.0 seconds: finished matcha latte hero shot. The vessel slowly rotates or the camera gently orbits. Foam settling, steam, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No neon green liquid, no hard synthetic layers, no powder cloud.
```

### Матча Латте на безлактозном Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Матча Латте на безлактозном.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot lactose-free milk and matcha, creamy pale natural green, not neon.
- Layers: soft matcha swirls during preparation; finished drink is uniform pale green or a gentle milk-to-matcha gradient.
- Top surface: smooth pale-green microfoam, optionally with tiny matcha dusting.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the vessel already contains warm lactose-free milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate or steamed lactose-free milk pours in, creating soft green swirls that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in one frame.
- 1.3-5.0 seconds: finished matcha latte hero shot. The vessel slowly rotates or the camera gently orbits. Foam settling, steam, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No neon green liquid, no hard synthetic layers, no powder cloud.
```

### Матча Латте на кокосовом молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Матча Латте на кокосовом молоке.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot coconut milk and matcha, creamy pale natural green, not neon.
- Layers: soft matcha swirls during preparation; finished drink is uniform pale green or a gentle milk-to-matcha gradient.
- Top surface: smooth pale-green microfoam, optionally with tiny matcha dusting.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the vessel already contains warm coconut milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate or steamed coconut milk pours in, creating soft green swirls that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in one frame.
- 1.3-5.0 seconds: finished matcha latte hero shot. The vessel slowly rotates or the camera gently orbits. Foam settling, steam, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No neon green liquid, no hard synthetic layers, no powder cloud.
```

### Матча Латте на миндальном молоке Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Матча Латте на миндальном молоке.
- Vessel: tall clear ribbed glass or ceramic cup, matching the provided item reference if available.
- Liquid: hot almond milk and matcha, creamy pale natural green, not neon.
- Layers: soft matcha swirls during preparation; finished drink is uniform pale green or a gentle milk-to-matcha gradient.
- Top surface: smooth pale-green microfoam, optionally with tiny matcha dusting.
- Hot-drink cue: very subtle steam, thin and realistic.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the vessel already contains warm almond milk or partially mixed pale matcha milk.
- 0.3-1.3 seconds: green matcha concentrate or steamed almond milk pours in, creating soft green swirls that blend gradually into creamy pale matcha green.
- The liquid must not jump from white to bright green or from green to white in one frame.
- 1.3-5.0 seconds: finished matcha latte hero shot. The vessel slowly rotates or the camera gently orbits. Foam settling, steam, matcha swirls, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No neon green liquid, no hard synthetic layers, no powder cloud.
```

### Молочный коктейль Ванильный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Молочный коктейль Ванильный.
- Vessel: tall clear glass.
- Liquid: thick vanilla milkshake, pale cream vanilla color, creamy and opaque.
- Texture: smooth glossy shake with slow heavy movement.
- Surface: thick soft ripples, optionally with minimal realistic vanilla accent.
- Temperature cue: cold creamy drink with faint condensation. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.3 seconds: thick vanilla milkshake pours slowly into the glass. The surface forms heavy glossy ripples that continue after the pour.
- Texture must stay thick and continuous; no watery liquid and no sudden frozen surface.
- 1.3-5.0 seconds: finished milkshake hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No whipped cream mountain unless requested, no neon color, no candy overload.
```

### Молочный коктейль Клубничный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Молочный коктейль Клубничный.
- Vessel: tall clear glass.
- Liquid: thick strawberry milkshake, soft natural pink strawberry color, creamy and opaque.
- Texture: smooth glossy shake with slow heavy movement.
- Surface: thick soft ripples, optionally with minimal realistic strawberry accent.
- Temperature cue: cold creamy drink with faint condensation. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.3 seconds: thick strawberry milkshake pours slowly into the glass. The surface forms heavy glossy ripples that continue after the pour.
- Texture must stay thick and continuous; no watery liquid and no sudden frozen surface.
- 1.3-5.0 seconds: finished milkshake hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No whipped cream mountain unless requested, no neon color, no candy overload.
```

### Молочный коктейль Манго-Маракуйя Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Молочный коктейль Манго-Маракуйя.
- Vessel: tall clear glass.
- Liquid: thick mango-passionfruit milkshake, pale golden tropical color, creamy and opaque.
- Texture: smooth glossy shake with slow heavy movement.
- Surface: thick soft ripples, optionally with minimal realistic mango-passionfruit accent.
- Temperature cue: cold creamy drink with faint condensation. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.3 seconds: thick mango-passionfruit milkshake pours slowly into the glass. The surface forms heavy glossy ripples that continue after the pour.
- Texture must stay thick and continuous; no watery liquid and no sudden frozen surface.
- 1.3-5.0 seconds: finished milkshake hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No whipped cream mountain unless requested, no neon color, no candy overload.
```

### Молочный коктейль Шоколадный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Молочный коктейль Шоколадный.
- Vessel: tall clear glass.
- Liquid: thick chocolate milkshake, creamy milk-chocolate brown, creamy and opaque.
- Texture: smooth glossy shake with slow heavy movement.
- Surface: thick soft ripples, optionally with minimal realistic cocoa accent.
- Temperature cue: cold creamy drink with faint condensation. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.3 seconds: thick chocolate milkshake pours slowly into the glass. The surface forms heavy glossy ripples that continue after the pour.
- Texture must stay thick and continuous; no watery liquid and no sudden frozen surface.
- 1.3-5.0 seconds: finished milkshake hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No whipped cream mountain unless requested, no neon color, no candy overload.
```

### Морс Клюква Вишня Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Морс Клюква Вишня.
- Vessel: clear glass or tall ribbed glass.
- Liquid: cranberry-cherry morse, deep ruby cranberry-cherry red, slightly translucent with natural berry/fruit depth.
- Garnish: optional subtle cherry or cranberry accent in the background only.
- Temperature cue: chilled drink with optional condensation; no steam unless specifically served hot.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: cranberry-cherry morse pours into the glass. Tiny bubbles and natural fruit color move as the liquid level rises.
- Color settles gradually and remains natural; no neon tint or instant flat surface.
- 1.2-5.0 seconds: finished morse hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No cocktail styling, no artificial neon color, no chunks floating unrealistically.
```

### Морс Клюква Лесные Ягоды Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Морс Клюква Лесные Ягоды.
- Vessel: clear glass or tall ribbed glass.
- Liquid: cranberry forest berry morse, dark berry-red with natural depth, slightly translucent with natural berry/fruit depth.
- Garnish: optional subtle forest berry accent in the background only.
- Temperature cue: chilled drink with optional condensation; no steam unless specifically served hot.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: cranberry forest berry morse pours into the glass. Tiny bubbles and natural fruit color move as the liquid level rises.
- Color settles gradually and remains natural; no neon tint or instant flat surface.
- 1.2-5.0 seconds: finished morse hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No cocktail styling, no artificial neon color, no chunks floating unrealistically.
```

### Морс Клюква Можжевельник Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Морс Клюква Можжевельник.
- Vessel: clear glass or tall ribbed glass.
- Liquid: cranberry-juniper morse, cranberry red with herbal depth, slightly translucent with natural berry/fruit depth.
- Garnish: optional subtle juniper accent in the background only.
- Temperature cue: chilled drink with optional condensation; no steam unless specifically served hot.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: cranberry-juniper morse pours into the glass. Tiny bubbles and natural fruit color move as the liquid level rises.
- Color settles gradually and remains natural; no neon tint or instant flat surface.
- 1.2-5.0 seconds: finished morse hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No cocktail styling, no artificial neon color, no chunks floating unrealistically.
```

### Морс Клюква Облепиха-Имбирь Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Морс Клюква Облепиха-Имбирь.
- Vessel: clear glass or tall ribbed glass.
- Liquid: cranberry sea-buckthorn ginger morse, warm orange-red with natural pulp brightness, slightly translucent with natural berry/fruit depth.
- Garnish: optional subtle sea-buckthorn or ginger accent in the background only.
- Temperature cue: chilled drink with optional condensation; no steam unless specifically served hot.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: cranberry sea-buckthorn ginger morse pours into the glass. Tiny bubbles and natural fruit color move as the liquid level rises.
- Color settles gradually and remains natural; no neon tint or instant flat surface.
- 1.2-5.0 seconds: finished morse hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, condensation, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No cocktail styling, no artificial neon color, no chunks floating unrealistically.
```

### Раф Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Раф.
- Vessel: 300 ml serving in a tall clear ribbed glass or clean ceramic cup, matching the provided item reference if available.
- Liquid: hot cream-coffee mixture, silky warm beige with a slight vanilla tone.
- Texture: velvety and lightly whipped, creamier than latte.
- Surface: smooth pale beige microfoam, optionally with very light vanilla sugar dust.
- Hot-drink cue: thin realistic steam, not a visible cloud.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: pale cream-and-coffee mixture pours into the vessel in a smooth continuous stream.
- The drink starts light caramel and becomes uniform warm beige through realistic blending, never through a single-frame morph.
- 1.2-5.0 seconds: finished raf hero shot. The vessel slowly rotates or the camera gently orbits. Silky surface motion, steam, reflections, and camera movement continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No black espresso phase, no whipped cream mountain, no cappuccino foam cap.
```

### Флэт Уайт Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Флэт Уайт.
- Vessel: short clear ribbed glass or low ceramic cup, matching the provided item reference if available.
- Liquid: hot smooth light caramel coffee, slightly lighter than cappuccino but stronger-looking than latte.
- Foam: thin velvety microfoam, flatter than cappuccino.
- Top surface: simple white heart or tulip latte art.
- Hot-drink cue: nearly invisible thin steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.2 seconds: the vessel already contains a small espresso base partially mixed with milk, medium caramel rather than black.
- 0.2-1.2 seconds: steamed milk pours gently into the coffee. The visible liquid lightens continuously from medium caramel to warm creamy tan through realistic swirling.
- 1.2-5.0 seconds: finished flat white hero shot. The drink slowly rotates or the camera gently orbits. Microfoam settling, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No sudden color jump from dark espresso to creamy white, no giant foam cap.
```

### Чай Гречишный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Гречишный.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot buckwheat tea, warm golden-brown roasted grain color, transparent and natural.
- Garnish: optional subtle buckwheat grains, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай Иван-Чай с Саган Дайля и можжевельником Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Иван-Чай с Саган Дайля и можжевельником.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot ivan tea with sagan-daila and juniper, clear warm amber herbal color, transparent and natural.
- Garnish: optional subtle juniper and herb sprig, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай Краснополянский Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Краснополянский.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot mountain herbal tea, warm amber-gold color, transparent and natural.
- Garnish: optional subtle herbal sprig, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай Молочный Улун Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Молочный Улун.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot milk oolong tea, pale golden oolong color with creamy aroma, transparent and natural.
- Garnish: optional subtle oolong leaves, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай Мятная малина Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Мятная малина.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot mint raspberry tea, warm ruby raspberry color, transparent and natural.
- Garnish: optional subtle mint leaf and raspberry, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай Таежный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай Таежный.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot taiga forest herbal tea, deep amber herbal color, transparent and natural.
- Garnish: optional subtle forest berry or herb accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с вишней Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с вишней.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot cherry tea, translucent ruby-red cherry color, transparent and natural.
- Garnish: optional subtle single cherry accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с грейпфрутом и бузиной Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с грейпфрутом и бузиной.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot grapefruit elderflower tea, pale pink citrus color, transparent and natural.
- Garnish: optional subtle grapefruit slice, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с клюквой и Можжевельником Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с клюквой и Можжевельником.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot cranberry juniper tea, ruby cranberry-red color, transparent and natural.
- Garnish: optional subtle juniper accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с малиной Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с малиной.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot raspberry tea, warm red-pink raspberry color, transparent and natural.
- Garnish: optional subtle raspberry accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с облепихой и имбирем Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с облепихой и имбирем.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot sea-buckthorn ginger tea, warm orange-gold color with natural pulp, transparent and natural.
- Garnish: optional subtle ginger or sea-buckthorn accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай с чабрецом Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай с чабрецом.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot thyme tea, clear warm amber color, transparent and natural.
- Garnish: optional subtle thyme sprig, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Чай черный Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Чай черный.
- Vessel: heat-safe clear glass or ceramic cup.
- Liquid: hot black tea, clear dark amber-black tea color, transparent and natural.
- Garnish: optional subtle simple tea leaf accent, realistic and secondary.
- Hot-drink cue: gentle steam drifting continuously.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight, soft ambient cafe lighting, calm tea-house mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred herbs, berries, citrus, grey sofa, relief wall texture, or small plant. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: hot tea pours into the vessel or hot water infuses the tea. Color blooms gradually through the liquid.
- Herbs, berries, citrus, or tea particles move subtly and naturally; no hard color jump and no frozen steam.
- 1.2-5.0 seconds: finished tea hero shot. The cup or glass slowly rotates or the camera gently pushes in. Steam, surface ripples, infusion particles, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No labeled tea bag, no coffee color unless black tea, no cocktail styling.
```

### Эспрессо Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Эспрессо.
- Vessel: small ceramic espresso cup or small clear espresso glass, compact and premium.
- Liquid: dark espresso, deep brown but not pure black.
- Surface: rich golden-brown crema with tiny bubbles and glossy highlights.
- Hot-drink cue: very subtle steam, almost invisible.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Warm natural daylight mixed with soft cafe ambient light.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.0 seconds: a narrow dark espresso stream pours into the small cup or glass. The liquid level rises naturally and golden crema forms gradually.
- The crema appears through physical extraction and settling, not as a sudden flat overlay.
- 1.0-5.0 seconds: finished espresso hero shot. The cup slowly rotates or the camera slowly pushes in. Crema movement, steam, reflections, and camera motion continue naturally.

Composition:
- Keep the full cup or glass centered and fully visible.
- Main drink body stays mostly between 28% and 70% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No ice, no condensation-heavy cold-drink styling, no oversized steam cloud.
- No huge cup, no cappuccino foam, no latte art, no sudden crema replacement.
```

### Эспрессо тоник Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: Эспрессо тоник.
- Vessel: tall clear ribbed glass with vertical grooves and a solid transparent base.
- Liquid: sparkling tonic with espresso, transparent amber-brown with dark coffee ribbons, transparent enough to see ice and bubbles.
- Ice: several clear realistic ice cubes.
- Surface: active fine carbonation bubbles and glossy cold surface.
- Temperature cue: condensation droplets on the glass. No steam.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-0.3 seconds: the glass already contains ice and sparkling tonic with visible rising bubbles.
- 0.3-1.3 seconds: espresso pours over the ice and tonic, forming natural ribbons through the clear fizz.
- The ribbons blend gradually while carbonation keeps rising; no sudden color flash and no disappearing bubbles.
- 1.3-5.0 seconds: finished tonic hero shot. The glass slowly rotates or the camera gently orbits. Bubbles, ice, condensation, liquid ribbons, and reflections continue moving.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No steam, no hot-drink styling, no disappearing ice, no floating ice outside the glass.
- No milk, no foam cap, no flat non-carbonated tonic, no disappearing bubbles.
```

### ЯБЛОЧНЫЙ ФРЕШ Prompt

```text
Create a photorealistic 5-second vertical product video for Aura Coffee, a modern local coffee shop.

Output:
- 9:16 vertical video, 5 seconds, 1080x1920 or higher.
- Smooth premium drink cinematography, mobile-first, muted, loop-friendly.
- No text, no app UI, no status bar, no price, no nutrition overlay, no buttons, no watermark.

Drink:
- Name: ЯБЛОЧНЫЙ ФРЕШ.
- Vessel: tall clear glass or rounded clear glass.
- Liquid: freshly squeezed apple fresh juice, pale golden apple juice, lightly translucent with tiny natural bubbles, natural and appetizing.
- Texture: realistic juice body with subtle pulp, tiny bubbles, and natural translucency.
- Temperature cue: lightly chilled freshness; optional faint condensation only if served cold.

Scene:
- Light wooden Aura Coffee table in a cozy modern cafe.
- Bright natural window light with a fresh cold-drink mood.
- Muted olive, beige, grey, and cream background, softly blurred.
- Optional blurred grey sofa, relief wall texture, small plant, or ribbed glass vase. Keep props secondary.

Video sequence:
- 0.0-1.2 seconds: apple fresh juice pours into the clear glass in a smooth continuous stream. Pulp and bubbles move naturally as the level rises.
- The color remains natural and consistent; no neon color and no instant frozen surface.
- 1.2-5.0 seconds: finished fresh juice hero shot. The glass slowly rotates or the camera gently orbits. Surface ripples, pulp movement, bubbles, reflections, and camera motion continue naturally.

Composition:
- Keep the full vessel centered and fully visible.
- Main drink body stays mostly between 22% and 74% of frame height.
- Leave clean top and bottom safe space for frontend overlays.
- The drink must still read clearly when cropped into a horizontal menu card.

Negative prompt:
- No UI, text, price, nutrition labels, icons, phone status bar, or watermark.
- No people, hands, faces, extra drinks, random logos, or third-party branding.
- No distorted vessel, duplicate vessel, floating cup, messy splash, fantasy effects, or cartoon style.
- No sudden color jump, no liquid morph, no instant ingredient replacement.
- Required smooth continuous lifecycle: pour/mix action tapers naturally into settling liquid, foam/ice/steam/reflections continue moving, and hero rotation or camera motion continues without interruption.
- No time-skip from active pouring to a completed still drink; it must not look like a minute passed between frames.
- No abrupt freeze after pouring or mixing, no still-frame hero shot, no sudden stop of liquid, foam, ice, steam, reflections, rotation, camera motion, or background parallax.
- No soda carbonation, no cocktail styling, no artificial fruit chunks, no cartoon apple props.
```

## Prompt Tweaking Checklist

Before generating a drink video, fill in:

1. Drink name exactly as it appears in the menu.
   For menu-specific prompts, keep the Cyrillic `Name:` line unchanged.
2. Hot or iced.
3. Vessel reference: tall ribbed glass, short ribbed glass, rounded clear glass,
   or ceramic cup.
4. Main liquid color.
5. Layers, if any.
6. Foam, crema, ice, condensation, steam, or topping details.
7. Preparation action for the first second.
8. Background choice: window/table, relief wall/grey sofa, or clean warm studio
   cafe setup.

After generation, reject outputs with:

- UI or text baked into the video;
- bad mobile crop;
- distorted vessel;
- changing glass shape between preparation and hero shot;
- unrealistic liquid or foam;
- drink too close to edges;
- people or hands;
- time-skip from active pouring or mixing to a completed drink;
- abrupt freeze after pouring or mixing;
- a still-frame hero shot with no continuing liquid, foam, ice, reflection,
  camera, or background motion;
- missing smooth drink lifecycle from preparation to pour tapering to settling
  to hero rotation or camera motion;
- low-quality poster frame around seconds `2.0-4.5`.
