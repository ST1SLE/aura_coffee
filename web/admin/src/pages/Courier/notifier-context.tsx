import { createContext, useContext, type ReactNode } from 'react';
import { useNotifier } from '@/components/ui/notifier';

type NotifierValue = ReturnType<typeof useNotifier>;

const NotifierContext = createContext<NotifierValue | null>(null);

export function CourierNotifierProvider({ children }: { children: ReactNode }) {
  const value = useNotifier();
  return (
    <NotifierContext.Provider value={value}>{children}</NotifierContext.Provider>
  );
}

export function useCourierNotifier(): NotifierValue {
  const ctx = useContext(NotifierContext);
  if (!ctx) {
    throw new Error('useCourierNotifier must be used inside <CourierNotifierProvider>');
  }
  return ctx;
}
