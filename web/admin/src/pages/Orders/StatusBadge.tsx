import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import type { OrderStatus } from '@/api/admin-orders';

// Цветовая карта статусов заказа (PDD §6.1, design.md Decision 6).
const STATUS_CLASSES: Record<OrderStatus, string> = {
  created: 'bg-gray-200 text-gray-800',
  paid: 'bg-blue-100 text-blue-800',
  preparing: 'bg-orange-100 text-orange-800',
  ready: 'bg-green-100 text-green-800',
  in_delivery: 'bg-purple-100 text-purple-800',
  completed: 'bg-neutral-100 text-neutral-700',
  cancelled: 'bg-red-100 text-red-800',
};

interface StatusBadgeProps {
  status: OrderStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const { t } = useTranslation();
  return (
    <Badge
      variant="outline"
      className={STATUS_CLASSES[status]}
      data-testid={`status-badge-${status}`}
    >
      {t(`pages.orders.status.${status}`)}
    </Badge>
  );
}
