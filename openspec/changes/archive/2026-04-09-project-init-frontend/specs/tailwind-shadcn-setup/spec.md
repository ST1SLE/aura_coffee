## ADDED Requirements

### Requirement: Shared Tailwind preset
The system SHALL have a shared Tailwind preset at `web/shared-config/tailwind-preset.js` defining brand colors, spacing scale, font stack, and border-radius tokens. Both SPAs SHALL extend this preset in their `tailwind.config.ts`.

#### Scenario: Both apps use consistent brand colors
- **WHEN** both SPAs are built
- **THEN** the generated CSS in both apps contains identical CSS custom properties for brand colors defined in the shared preset

#### Scenario: Preset change propagates to both apps
- **WHEN** a color value is changed in `web/shared-config/tailwind-preset.js`
- **THEN** both SPAs reflect the new color after rebuild

### Requirement: Tailwind CSS configured in both SPAs
Both SPAs SHALL have Tailwind CSS installed and configured with `postcss` and `autoprefixer`. The main CSS file SHALL include `@tailwind base`, `@tailwind components`, and `@tailwind utilities` directives.

#### Scenario: Tailwind utility classes work
- **WHEN** a component uses Tailwind utility classes (e.g., `className="text-lg p-4"`)
- **THEN** the corresponding CSS is included in the build output

### Requirement: shadcn/ui initialized
Both SPAs SHALL have shadcn/ui initialized with the `components.json` config file. The `components/ui/` directory SHALL be created. At least one component (Button) SHALL be added to verify the setup.

#### Scenario: shadcn Button component renders
- **WHEN** the app renders a `<Button>` component from `@/components/ui/button`
- **THEN** the button displays with correct styling from the shared Tailwind preset

### Requirement: Mobile-first responsive breakpoints
The Tailwind config SHALL define breakpoints matching PDD §4.4: mobile (default, 320px min), tablet (`md: 768px`), desktop (`lg: 1024px`).

#### Scenario: Responsive classes apply at correct breakpoints
- **WHEN** a component uses `className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3"`
- **THEN** the layout changes from 1 column to 2 at 768px and to 3 at 1024px
