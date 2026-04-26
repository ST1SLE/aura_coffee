import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';

// START_MODULE_CONTRACT
//   PURPOSE: Lightweight inline-banner notification system — a useNotifier hook
//            that owns a queue + auto-dismiss timer, and a presentational
//            NotificationList that renders the queue with per-variant styling.
//            No external toast library; sized for the admin SPA's small needs.
//   SCOPE:   Used by every admin page that needs success/error/info banners.
//            CourierShell exposes the same hook through React context so child
//            tabs can dispatch notifications upward.
//   DEPENDS: react, lucide-react (X icon), @/lib/utils (cn).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   useNotifier      - owns notifications array + notify/dismiss callbacks
//   NotificationList - renders the queue at fixed bottom-right with dismiss
// END_MODULE_MAP

type NotifyVariant = 'error' | 'success' | 'info';

interface Notification {
  id: number;
  message: string;
  variant: NotifyVariant;
}

let _nextId = 0;

// START_CONTRACT: useNotifier
//   PURPOSE: React hook that owns a notifications queue + provides notify(message,
//            variant) and dismiss(id). Auto-dismisses each banner after 4s.
//   INPUTS:  none
//   OUTPUTS: { notifications: Notification[], notify: (msg, variant?) => void,
//              dismiss: (id: number) => void }
//   SIDE_EFFECTS: setTimeout for auto-dismiss; component-local state.
// END_CONTRACT: useNotifier
// Хук для показа inline-баннеров без внешней зависимости
export function useNotifier() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const notify = useCallback((message: string, variant: NotifyVariant = 'info') => {
    const id = _nextId++;
    setNotifications((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return { notifications, notify, dismiss };
}

const variantClasses: Record<NotifyVariant, string> = {
  error: 'bg-destructive text-destructive-foreground',
  success: 'bg-green-600 text-white',
  info: 'bg-secondary text-secondary-foreground',
};

interface NotificationListProps {
  notifications: Notification[];
  onDismiss: (id: number) => void;
}

export function NotificationList({ notifications, onDismiss }: NotificationListProps) {
  if (notifications.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {notifications.map((n) => (
        <div
          key={n.id}
          className={cn(
            'flex items-start gap-2 rounded-md px-4 py-3 text-sm shadow-lg',
            variantClasses[n.variant],
          )}
        >
          <span className="flex-1">{n.message}</span>
          <button
            onClick={() => onDismiss(n.id)}
            className="shrink-0 opacity-70 hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
