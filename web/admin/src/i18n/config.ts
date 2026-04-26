import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import ruCommon from './locales/ru/common.json';
import enCommon from './locales/en/common.json';

// START_MODULE_CONTRACT
//   PURPOSE: i18next bootstrap — registers locale detector, react-i18next bridge,
//            and bundled RU/EN namespaces for the staff SPA.
//   SCOPE:   Loaded once at app startup (imported by main.tsx). No exports beyond
//            the configured i18n singleton.
//   DEPENDS: i18next, react-i18next, i18next-browser-languagedetector,
//            ./locales/{ru,en}/common.json
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (bilingual RU/EN).
//   ROLE:    RUNTIME
//   MAP_MODE: NONE
// END_MODULE_CONTRACT

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: { common: ruCommon },
      en: { common: enCommon },
    },
    defaultNS: 'common',
    fallbackLng: 'en',
    lng: undefined,
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'i18nextLng',
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
