import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { getAccessToken } from '@/api/client';
import { getRole, type StaffRole } from '@/lib/auth';

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: StaffRole[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
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

  if (allowedRoles) {
    const role = getRole();
    if (role === null || !allowedRoles.includes(role)) {
      // UX-подсказка. Сервер — источник истины (INV-010).
      const target = role === 'courier' ? '/courier' : '/';
      return <Navigate to={target} replace />;
    }
  }

  return <>{children}</>;
}
