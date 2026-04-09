## ADDED Requirements

### Requirement: Customer SPA project structure
The system SHALL have a React 19 + TypeScript application at `web/customer/` with a valid `package.json`, `tsconfig.json`, and Vite config (`vite.config.ts`). The app SHALL render a root `<App />` component.

#### Scenario: Customer app starts in dev mode
- **WHEN** developer runs `npm run dev` in `web/customer/`
- **THEN** Vite dev server starts on port 5173 and serves the React app with HMR enabled

#### Scenario: Customer app builds for production
- **WHEN** developer runs `npm run build` in `web/customer/`
- **THEN** Vite produces a production bundle in `web/customer/dist/` with no TypeScript errors

### Requirement: Admin SPA project structure
The system SHALL have a React 19 + TypeScript application at `web/admin/` with a valid `package.json`, `tsconfig.json`, and Vite config (`vite.config.ts`). The app SHALL render a root `<App />` component.

#### Scenario: Admin app starts in dev mode
- **WHEN** developer runs `npm run dev` in `web/admin/`
- **THEN** Vite dev server starts on port 5174 and serves the React app with HMR enabled

#### Scenario: Admin app builds for production
- **WHEN** developer runs `npm run build` in `web/admin/`
- **THEN** Vite produces a production bundle in `web/admin/dist/` with no TypeScript errors

### Requirement: TypeScript strict mode
Both SPAs SHALL use TypeScript with `strict: true` in `tsconfig.json`. The `target` SHALL be `ES2022` and `moduleResolution` SHALL be `bundler`.

#### Scenario: Type errors are caught at build time
- **WHEN** a source file contains a type error
- **THEN** `npm run build` fails with a descriptive TypeScript error

### Requirement: Path aliases
Both SPAs SHALL configure the `@/` path alias pointing to `src/` directory via `tsconfig.json` paths and Vite resolve alias.

#### Scenario: Import using path alias
- **WHEN** a component imports `from '@/components/Button'`
- **THEN** the import resolves to `src/components/Button` and the app builds successfully
