import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '@/App';
import '@/i18n/config';
import '@/index.css';

// START_MODULE_CONTRACT
//   PURPOSE: Browser entry point — boot React StrictMode + App into #root.
//            Importing '@/i18n/config' for its initialization side-effect must
//            happen before App renders so useTranslation has resources ready.
//            Customer typography is self-hosted through Fontsource assets
//            declared in index.css.
//   SCOPE:   No exports; this file just runs createRoot().render() at module load.
//   DEPENDS: react, react-dom/client, @/App, @/i18n/config (side-effect),
//            @/index.css.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER.
//   ROLE:    RUNTIME
//   MAP_MODE: NONE
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   (no public exports — module is executed for side effects only)
// END_MODULE_MAP

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
