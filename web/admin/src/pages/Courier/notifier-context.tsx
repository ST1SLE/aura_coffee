import { createContext, useContext, type ReactNode } from 'react';
import { useNotifier } from '@/components/ui/notifier';

// START_MODULE_CONTRACT
//   PURPOSE: Wrap the shared useNotifier in a React context so the courier
//            tabs can dispatch toasts that the CourierShell renders, without
//            prop drilling.
//   SCOPE:   Used by CourierShell + AvailableTab + MineTab.
//   DEPENDS: react, @/components/ui/notifier (useNotifier).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CourierNotifierProvider - wraps children with a useNotifier-backed context
//   useCourierNotifier      - hook to read the notifier value (throws if outside provider)
// END_MODULE_MAP

type NotifierValue = ReturnType<typeof useNotifier>;

const NotifierContext = createContext<NotifierValue | null>(null);

// START_CONTRACT: CourierNotifierProvider
//   PURPOSE: Instantiate one useNotifier and publish it via context to its
//            descendants.
//   INPUTS:  { children: ReactNode }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: state owned by the underlying useNotifier hook.
// END_CONTRACT: CourierNotifierProvider
export function CourierNotifierProvider({ children }: { children: ReactNode }) {
  const value = useNotifier();
  return (
    <NotifierContext.Provider value={value}>{children}</NotifierContext.Provider>
  );
}

// START_CONTRACT: useCourierNotifier
//   PURPOSE: Consume the courier notifier context. Throws if used outside the
//            provider so misconfigured trees fail loudly during development.
//   INPUTS:  none.
//   OUTPUTS: NotifierValue.
//   SIDE_EFFECTS: throws on misuse.
// END_CONTRACT: useCourierNotifier
export function useCourierNotifier(): NotifierValue {
  const ctx = useContext(NotifierContext);
  if (!ctx) {
    throw new Error('useCourierNotifier must be used inside <CourierNotifierProvider>');
  }
  return ctx;
}
