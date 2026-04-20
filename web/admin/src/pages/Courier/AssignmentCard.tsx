import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { CourierAssignmentResponse } from '@/api/courier';

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

  return (
    <article className="w-full md:w-1/2 rounded-md border bg-card text-card-foreground p-4 flex flex-col gap-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-medium">{time}</div>
        <div className="text-sm font-semibold">
          {formatRoubles(assignment.total)}
        </div>
      </div>
      <div className="text-sm text-muted-foreground break-words">
        {assignment.delivery_address.address_line}
      </div>
      {action ? <div className="mt-auto">{action}</div> : null}
    </article>
  );
}
