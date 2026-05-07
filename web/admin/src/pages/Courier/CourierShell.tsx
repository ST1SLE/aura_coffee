import { Outlet } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { logout } from '@/api/client';
import { BrandMark, BrandWordmark } from '@/components/BrandMark';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { Button } from '@/components/ui/button';
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
  const { t } = useTranslation();
  const { notifications, dismiss } = useCourierNotifier();
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border/80 bg-card/95 px-4 py-3 shadow-[0_8px_24px_rgba(26,37,33,0.06)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <BrandMark
              decorative
              className="h-10 w-10 shrink-0 object-contain drop-shadow-[0_10px_18px_rgba(26,37,33,0.14)]"
            />
            <BrandWordmark
              decorative
              className="h-5 w-auto max-w-[8rem] object-contain"
            />
            <span className="sr-only">{t('appTitle')}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="logout-courier"
              onClick={logout}
            >
              <LogOut aria-hidden="true" />
              {t('nav.logout')}
            </Button>
            <LanguageSwitcher />
          </div>
        </div>
      </header>
      <main className="flex-1 px-4 py-5 sm:px-6">
        <div className="mx-auto w-full max-w-4xl">
          <Outlet />
        </div>
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
