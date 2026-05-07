import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock3, MapPin, ReceiptText } from 'lucide-react';
import type { CourierAssignmentResponse } from '@/api/courier';

// START_MODULE_CONTRACT
//   PURPOSE: Card representation of one courier assignment — requested time,
//            total, optional address line visibility, optional action slot.
//            Pure presentation.
//   SCOPE:   Used by AvailableTab and MineTab.
//   DEPENDS: react-i18next, @/api/courier type.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (courier views).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AssignmentCard - single-assignment card with time, total, optional address, action slot
// END_MODULE_MAP

interface AssignmentCardProps {
  assignment: CourierAssignmentResponse;
  action?: ReactNode;
  showAddress?: boolean;
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

// START_CONTRACT: AssignmentCard
//   PURPOSE: Render one courier assignment card while allowing the caller to
//            suppress delivery address details for pre-assignment feeds.
//   INPUTS:  assignment: CourierAssignmentResponse — normalized backend DTO
//            action?: ReactNode — optional footer action button
//            showAddress?: boolean — false hides address even if DTO contains it.
//   OUTPUTS: JSX.Element — courier assignment card.
//   SIDE_EFFECTS: none.
//   LINKS:   INV-010, INV-013 (available feed must minimize delivery PII).
// END_CONTRACT: AssignmentCard
export function AssignmentCard({
  assignment,
  action,
  showAddress = true,
}: AssignmentCardProps) {
  const { t } = useTranslation();
  const asapLabel = t('courier.fields.requestedAsap');
  const time = formatRequestedTime(assignment.requested_time, asapLabel);
  const address =
    showAddress && assignment.delivery_address.address_line
      ? assignment.delivery_address.address_line
      : t('courier.fields.addressHidden');

  return (
    <article
      data-testid={`courier-assignment-${assignment.id}`}
      className="admin-surface flex min-h-[10rem] w-full flex-col gap-4 p-4 text-card-foreground"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold">
          <Clock3
            className="h-4 w-4 shrink-0 text-primary"
            aria-hidden="true"
          />
          <span className="truncate">{time}</span>
        </div>
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ReceiptText
            className="h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <span className="admin-numeric">
            {formatRoubles(assignment.total)}
          </span>
        </div>
      </div>
      <div className="flex gap-2 rounded-md bg-secondary/55 p-3 text-sm text-muted-foreground">
        <MapPin
          className="mt-0.5 h-4 w-4 shrink-0 text-primary"
          aria-hidden="true"
        />
        <span className="min-w-0 break-words">{address}</span>
      </div>
      {action ? <div className="mt-auto">{action}</div> : null}
    </article>
  );
}
