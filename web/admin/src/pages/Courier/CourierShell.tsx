import { Outlet } from 'react-router-dom';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { NotificationList } from '@/components/ui/notifier';
import {
  CourierNotifierProvider,
  useCourierNotifier,
} from '@/pages/Courier/notifier-context';

// START_MODULE_CONTRACT
//   PURPOSE: Courier-only shell — wraps the courier route subtree in a
//            NotifierProvider so child tabs can dispatch toasts upward, and
//            renders header (language switcher) + main outlet + bottom-corner
//            notifications.
//   SCOPE:   Mounted as the parent route of /courier in App.tsx, behind a
//            ProtectedRoute that allows courier only.
//   DEPENDS: react-router-dom, @/components/LanguageSwitcher, @/components/ui/notifier,
//            ./notifier-context.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (courier views),
//            INV-002 (server enforces courier scope on assignment endpoints),
//            INV-010 (courier sees only assignment data; no menu/users/settings).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CourierShell - courier route layout with shared notifier context
// END_MODULE_MAP

function ShellBody() {
  const { notifications, dismiss } = useCourierNotifier();
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="border-b px-4 py-3 flex items-center justify-end">
        <LanguageSwitcher />
      </header>
      <main className="flex-1 p-4">
        <Outlet />
      </main>
      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}

// START_CONTRACT: CourierShell
//   PURPOSE: Provide the courier route layout — install NotifierProvider so the
//            shared notifier is available to AvailableTab and MineTab without
//            prop drilling, then render the inner ShellBody.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: none beyond context provisioning; the inner notifier owns the timers.
//   LINKS:   INV-002, INV-010 (this shell is only mounted for courier
//            users; ProtectedRoute upstream gates access).
// END_CONTRACT: CourierShell
export function CourierShell() {
  return (
    <CourierNotifierProvider>
      <ShellBody />
    </CourierNotifierProvider>
  );
}
