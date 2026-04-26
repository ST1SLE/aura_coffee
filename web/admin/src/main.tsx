import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from '@/App';
import '@/i18n/config';
import '@/index.css';

// START_MODULE_CONTRACT
//   PURPOSE: SPA entry point — boots i18next via side-effect import, creates
//            the React Query client, and mounts <App/> into #root under
//            <StrictMode>. No exports.
//   SCOPE:   The Vite bundle entry referenced from index.html.
//   DEPENDS: react, react-dom, @tanstack/react-query, @/App, @/i18n/config, css.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: NONE
// END_MODULE_CONTRACT

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
