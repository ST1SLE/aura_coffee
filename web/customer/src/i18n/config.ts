import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import ruCommon from './locales/ru/common.json';
import enCommon from './locales/en/common.json';

// START_MODULE_CONTRACT
//   PURPOSE: i18next bootstrap — registers LanguageDetector + react-i18next
//            integration, loads ru/en common namespace JSON, and configures
//            localStorage-cached language detection. Imported for side-effect
//            from main.tsx.
//   SCOPE:   default-export of the configured i18next instance.
//   DEPENDS: i18next, react-i18next, i18next-browser-languagedetector,
//            ./locales/{ru,en}/common.json.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4 bilingual UI.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   default  - configured i18next instance (already .init()-ed)
// END_MODULE_MAP

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
