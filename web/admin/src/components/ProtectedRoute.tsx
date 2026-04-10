import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { getAccessToken } from '@/api/client';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = getAccessToken();
  const location = useLocation();

  if (!token) {
    const returnUrl = location.pathname + location.search;
    return (
      <Navigate
        to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`}
        replace
      />
    );
  }

  return <>{children}</>;
}
