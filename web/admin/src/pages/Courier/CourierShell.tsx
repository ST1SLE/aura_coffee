import { Outlet } from 'react-router-dom';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { NotificationList } from '@/components/ui/notifier';
import {
  CourierNotifierProvider,
  useCourierNotifier,
} from '@/pages/Courier/notifier-context';

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

export function CourierShell() {
  return (
    <CourierNotifierProvider>
      <ShellBody />
    </CourierNotifierProvider>
  );
}
