import { useContext } from 'react';
import { AuthContext } from './AuthProvider';
import type { AuthContextValue } from './AuthProvider';

// START_MODULE_CONTRACT
//   PURPOSE: useAuth hook — typed accessor for AuthContext that throws if used
//            outside the provider, so consumers don't need to handle null.
//   SCOPE:   useAuth.
//   DEPENDS: react (useContext), ./AuthProvider.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6 OTP flow.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   useAuth  - non-nullable AuthContextValue accessor (throws when unprovided)
// END_MODULE_MAP

// START_CONTRACT: useAuth
//   PURPOSE: Read the current AuthContextValue or throw a developer-friendly
//            error if the hook is called outside <AuthProvider>.
//   INPUTS:  none.
//   OUTPUTS: AuthContextValue.
//   SIDE_EFFECTS: throws Error when context is null. INV-002 — the value
//                 returned here is UX state only; server enforces.
//   LINKS:   AuthProvider.AuthContextValue.
// END_CONTRACT: useAuth
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
