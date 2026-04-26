// START_MODULE_CONTRACT
//   PURPOSE: Compatibility barrel — older import path '@/pages/DashboardPage'
//            re-exports the actual implementation under './Dashboard'.
//   SCOPE:   Single re-export.
//   DEPENDS: ./Dashboard
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    BARREL
//   MAP_MODE: NONE
// END_MODULE_CONTRACT
export { DashboardPage } from './Dashboard';
