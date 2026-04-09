## 1. Shared Config

- [x] 1.1 [web-customer] Create `web/shared-config/tailwind-preset.js` with brand colors, spacing, font stack, border-radius tokens, and responsive breakpoints (mobile default, md: 768px, lg: 1024px)

## 2. Customer SPA — Project Init

- [x] 2.1 [web-customer] Create `web/customer/package.json` with React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router, Vitest, ESLint, Prettier dependencies
- [x] 2.2 [web-customer] Create `web/customer/tsconfig.json` with strict mode, ES2022 target, bundler moduleResolution, `@/` path alias
- [x] 2.3 [web-customer] Create `web/customer/vite.config.ts` with React plugin, `@/` resolve alias, dev server port 5173
- [x] 2.4 [web-customer] Create `web/customer/tailwind.config.ts` extending shared preset from `../shared-config/tailwind-preset.js`
- [x] 2.5 [web-customer] Create `web/customer/postcss.config.js` with tailwindcss and autoprefixer
- [x] 2.6 [web-customer] Create `web/customer/src/index.css` with Tailwind directives (`@tailwind base/components/utilities`)
- [x] 2.7 [web-customer] Create `web/customer/src/main.tsx` — React entry point rendering `<App />` into root div
- [x] 2.8 [web-customer] Create `web/customer/index.html` — HTML entry point with root div and Vite script tag
- [x] 2.9 [web-customer] Create `web/customer/components.json` — run shadcn/ui init, add Button component to `src/components/ui/`
- [x] 2.10 [web-customer] Create `web/customer/.prettierrc` with shared formatting rules
- [x] 2.11 [web-customer] Create `web/customer/eslint.config.js` with typescript-eslint and react-hooks plugins

## 3. Customer SPA — i18n

- [x] 3.1 [web-customer] Create `web/customer/src/i18n/config.ts` — i18next init with ru default, en fallback, localStorage detection
- [x] 3.2 [web-customer] Create `web/customer/src/i18n/locales/ru/common.json` with basic UI strings (app title, nav labels, placeholder text)
- [x] 3.3 [web-customer] Create `web/customer/src/i18n/locales/en/common.json` with matching English translations
- [x] 3.4 [web-customer] Create `web/customer/src/components/LanguageSwitcher.tsx` — toggle between RU/EN

## 4. Customer SPA — Routing & Layout

- [x] 4.1 [web-customer] Create `web/customer/src/App.tsx` with React Router `<BrowserRouter>` and route definitions
- [x] 4.2 [web-customer] Create `web/customer/src/components/Layout.tsx` — app shell with header (title + LanguageSwitcher) and main content area
- [x] 4.3 [web-customer] Create `web/customer/src/pages/HomePage.tsx` — placeholder for Menu
- [x] 4.4 [web-customer] Create `web/customer/src/pages/CartPage.tsx` — placeholder
- [x] 4.5 [web-customer] Create `web/customer/src/pages/CheckoutPage.tsx` — placeholder
- [x] 4.6 [web-customer] Create `web/customer/src/pages/OrdersPage.tsx` — placeholder
- [x] 4.7 [web-customer] Create `web/customer/src/pages/ProfilePage.tsx` — placeholder
- [x] 4.8 [web-customer] Create `web/customer/src/pages/NotFoundPage.tsx` — 404 placeholder

## 5. Customer SPA — Testing

- [x] 5.1 [web-customer] Create `web/customer/vitest.config.ts` with jsdom environment and @testing-library/react
- [x] 5.2 [web-customer] Create `web/customer/src/App.test.tsx` — smoke test: App renders without crashing

## 6. Admin SPA — Project Init

- [x] 6.1 [web-admin] Create `web/admin/package.json` with React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router, Vitest, ESLint, Prettier dependencies
- [x] 6.2 [web-admin] Create `web/admin/tsconfig.json` with strict mode, ES2022 target, bundler moduleResolution, `@/` path alias
- [x] 6.3 [web-admin] Create `web/admin/vite.config.ts` with React plugin, `@/` resolve alias, dev server port 5174
- [x] 6.4 [web-admin] Create `web/admin/tailwind.config.ts` extending shared preset from `../shared-config/tailwind-preset.js`
- [x] 6.5 [web-admin] Create `web/admin/postcss.config.js` with tailwindcss and autoprefixer
- [x] 6.6 [web-admin] Create `web/admin/src/index.css` with Tailwind directives
- [x] 6.7 [web-admin] Create `web/admin/src/main.tsx` — React entry point rendering `<App />` into root div
- [x] 6.8 [web-admin] Create `web/admin/index.html` — HTML entry point with root div and Vite script tag
- [x] 6.9 [web-admin] Create `web/admin/components.json` — run shadcn/ui init, add Button component to `src/components/ui/`
- [x] 6.10 [web-admin] Create `web/admin/.prettierrc` with shared formatting rules
- [x] 6.11 [web-admin] Create `web/admin/eslint.config.js` with typescript-eslint and react-hooks plugins

## 7. Admin SPA — i18n

- [x] 7.1 [web-admin] Create `web/admin/src/i18n/config.ts` — i18next init with ru default, en fallback, localStorage detection
- [x] 7.2 [web-admin] Create `web/admin/src/i18n/locales/ru/common.json` with admin UI strings (dashboard, orders, menu, users, promos, settings)
- [x] 7.3 [web-admin] Create `web/admin/src/i18n/locales/en/common.json` with matching English translations
- [x] 7.4 [web-admin] Create `web/admin/src/components/LanguageSwitcher.tsx` — toggle between RU/EN

## 8. Admin SPA — Routing & Layout

- [x] 8.1 [web-admin] Create `web/admin/src/App.tsx` with React Router `<BrowserRouter>` and route definitions
- [x] 8.2 [web-admin] Create `web/admin/src/components/Layout.tsx` — app shell with sidebar navigation and header
- [x] 8.3 [web-admin] Create `web/admin/src/pages/DashboardPage.tsx` — placeholder
- [x] 8.4 [web-admin] Create `web/admin/src/pages/OrdersPage.tsx` — placeholder
- [x] 8.5 [web-admin] Create `web/admin/src/pages/MenuPage.tsx` — placeholder
- [x] 8.6 [web-admin] Create `web/admin/src/pages/UsersPage.tsx` — placeholder
- [x] 8.7 [web-admin] Create `web/admin/src/pages/PromosPage.tsx` — placeholder
- [x] 8.8 [web-admin] Create `web/admin/src/pages/SettingsPage.tsx` — placeholder
- [x] 8.9 [web-admin] Create `web/admin/src/pages/NotFoundPage.tsx` — 404 placeholder

## 9. Admin SPA — Testing

- [x] 9.1 [web-admin] Create `web/admin/vitest.config.ts` with jsdom environment and @testing-library/react
- [x] 9.2 [web-admin] Create `web/admin/src/App.test.tsx` — smoke test: App renders without crashing

## 10. Infrastructure

- [x] 10.1 [web-customer] Create `deploy/nginx/nginx.conf` — reverse proxy: `/` → customer:5173, `/admin` → admin:5174, `/api` → core-api:8000
- [x] 10.2 [web-customer] Add `web-customer` service to `docker-compose.yml` — Vite dev server with volume mount for HMR
- [x] 10.3 [web-admin] Add `web-admin` service to `docker-compose.yml` — Vite dev server with volume mount for HMR
- [x] 10.4 [web-customer] Add `nginx` service to `docker-compose.yml` — depends on web-customer and web-admin

## 11. Dev Scripts

- [x] 11.1 [web-customer] Create `scripts/lint-frontend.sh` — runs ESLint on both `web/customer/` and `web/admin/`
- [x] 11.2 [web-customer] Create `scripts/format-frontend.sh` — runs Prettier on both `web/customer/` and `web/admin/`
