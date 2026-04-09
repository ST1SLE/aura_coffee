## ADDED Requirements

### Requirement: react-i18next configured in both SPAs
Both SPAs SHALL have `react-i18next` installed and configured with `i18next` and `i18next-browser-languagedetector`. The default language SHALL be `ru`. The fallback language SHALL be `en`.

#### Scenario: App renders with Russian text by default
- **WHEN** the app loads without a stored language preference
- **THEN** UI text is displayed in Russian

#### Scenario: App falls back to English for missing keys
- **WHEN** a translation key is missing from the `ru` namespace
- **THEN** the English translation is displayed instead

### Requirement: Translation namespace structure
Each SPA SHALL store translations in `src/i18n/locales/{lang}/{namespace}.json`. The initial namespace SHALL be `common` containing basic UI strings (app title, navigation labels, placeholder text).

#### Scenario: Translation files exist for both languages
- **WHEN** the app is initialized
- **THEN** `src/i18n/locales/ru/common.json` and `src/i18n/locales/en/common.json` exist with matching keys

### Requirement: Language persistence
The selected language SHALL be persisted in `localStorage` under the key `i18nextLng`. On subsequent visits, the app SHALL use the stored language.

#### Scenario: Language preference persists across sessions
- **WHEN** user switches language to English and reloads the page
- **THEN** the app loads with English text

### Requirement: Language switcher component
Both SPAs SHALL include a `LanguageSwitcher` component that toggles between RU and EN. The component SHALL be placed in the app layout (header or navigation area).

#### Scenario: User switches language
- **WHEN** user clicks the language switcher
- **THEN** all UI text immediately changes to the selected language without page reload
