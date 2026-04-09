## Affected Modules

- **[web-customer]**

## Design

### 1. Desktop Nav in Layout Header

Layout header MUST be extended with an inline nav visible at `md:` and above.

```
┌──────────────────────────────────────────────────────────────┐
│  [Aura Coffee]   [Меню] [Корзина] [Заказы] [Профиль]  [Выйти] [EN] │
└──────────────────────────────────────────────────────────────┘
```

- Nav container: `hidden md:flex items-center gap-4` inside header, between logo and LanguageSwitcher
- Links: same `<Link>` elements as bottom nav, styled with `text-sm text-muted-foreground hover:text-foreground`
- Logout button: `<button>` calling `logout()` from `useAuth()`, then `navigate('/login')`. Styled as ghost/text to match nav links visually. Placed after Profile link, before LanguageSwitcher.
- LanguageSwitcher MUST remain rightmost element in header.

### 2. Logout Button in ProfilePage

ProfilePage MUST include a logout button at the bottom of the form area.

- Uses `useAuth().logout()` + `useNavigate()` to redirect to `/login`
- Styled as `variant="outline"` with destructive color hint (`text-destructive`) to signal the action
- Full width (`w-full`) within the `max-w-md` container

### 3. Mobile Safe Area

`index.html` viewport meta MUST be updated to `viewport-fit=cover`.

Bottom nav MUST add `pb-[env(safe-area-inset-bottom)]` — achieved via Tailwind arbitrary value or inline style `paddingBottom: env(safe-area-inset-bottom)`.

### 4. Mobile Tap Targets

Bottom nav links MUST have minimum 44px touch target. Add `py-2 px-3` padding and `flex flex-col items-center` for consistent sizing.

### 5. Translation Keys

ADDED `nav.logout`:
- `ru/common.json`: `"logout": "Выйти"`
- `en/common.json`: `"logout": "Sign Out"`

ADDED `pages.profile.logout`:
- `ru/common.json`: `"logout": "Выйти из аккаунта"`
- `en/common.json`: `"logout": "Sign Out"`

## Decisions

- Logout in header uses text-button style (not icon) — consistent with current text-only nav
- No active-link highlighting in this change — can be added later
- Desktop nav reuses same translation keys as mobile bottom nav
- Safe-area padding uses inline style for `env()` — Tailwind does not natively support `env()` in JIT without plugin
