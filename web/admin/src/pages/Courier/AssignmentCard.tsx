import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { CourierAssignmentResponse } from '@/api/courier';

// START_MODULE_CONTRACT
//   PURPOSE: Card representation of one courier assignment — requested time,
//            total, optional address line, optional action slot. Pure presentation.
//   SCOPE:   Used by AvailableTab and MineTab.
//   DEPENDS: react-i18next, @/api/courier type.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (courier views).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AssignmentCard - single-assignment card with time, total, address, action slot
// END_MODULE_MAP

interface AssignmentCardProps {
  assignment: CourierAssignmentResponse;
  action?: ReactNode;
}

function formatRoubles(kopecks: number): string {
  const roubles = kopecks / 100;
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(roubles);
}

function formatRequestedTime(iso: string | null, asapLabel: string): string {
  if (!iso) return asapLabel;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return asapLabel;
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export function AssignmentCard({ assignment, action }: AssignmentCardProps) {
  const { t } = useTranslation();
  const asapLabel = t('courier.fields.requestedAsap');
  const time = formatRequestedTime(assignment.requested_time, asapLabel);
  const address =
    assignment.delivery_address.address_line ?? t('courier.fields.addressHidden');

  return (
    <article className="w-full md:w-1/2 rounded-md border bg-card text-card-foreground p-4 flex flex-col gap-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-medium">{time}</div>
        <div className="text-sm font-semibold">
          {formatRoubles(assignment.total)}
        </div>
      </div>
      <div className="text-sm text-muted-foreground break-words">
        {address}
      </div>
      {action ? <div className="mt-auto">{action}</div> : null}
    </article>
  );
}
