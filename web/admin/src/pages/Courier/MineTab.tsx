import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  deliverAssignment,
  listMine,
  pickupAssignment,
  type CourierAssignmentResponse,
  type CourierAssignmentStatus,
} from '@/api/courier';
import { AssignmentCard } from '@/pages/Courier/AssignmentCard';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Tab listing the courier's claimed assignments with role-driven
//            action button (Pickup or Deliver) per assignment status. Polls
//            every 5s and invalidates on each successful mutation.
//   SCOPE:   Used only by CourierPage.
//   DEPENDS: react-i18next, @tanstack/react-query, @/api/courier,
//            ./AssignmentCard, ui Button.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md,
//            INV-002 (server enforces courier scope),
//            INV-010 (no PII beyond address),
//            INV-016 (pickup/deliver are state-machine transitions).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MineTab - polled list of own assignments with status-driven action button
// END_MODULE_MAP

interface StatusAction {
  label: string;
  mutationFn: (id: string) => Promise<CourierAssignmentResponse>;
}

function getStatusAction(
  status: CourierAssignmentStatus,
  t: (key: string) => string,
): StatusAction | null {
  if (status === 'COURIER_ASSIGNED') {
    return {
      label: t('courier.actions.pickup'),
      mutationFn: pickupAssignment,
    };
  }
  if (status === 'PICKED_UP') {
    return {
      label: t('courier.actions.deliver'),
      mutationFn: deliverAssignment,
    };
  }
  return null;
}

// START_CONTRACT: MineTab
//   PURPOSE: Poll listMine every 5s while visible; for each assignment derive
//            the appropriate next-step action (Pickup for COURIER_ASSIGNED,
//            Deliver for PICKED_UP) and POST it via the courier API on click.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET listMine; POST pickupAssignment / deliverAssignment;
//            query invalidation on success.
//   LINKS:   INV-002, INV-010, INV-016 (each button triggers a state-machine transition).
// END_CONTRACT: MineTab
export function MineTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const query = useQuery<CourierAssignmentResponse[]>({
    queryKey: ['courier', 'mine'],
    queryFn: listMine,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const mutation = useMutation({
    mutationFn: ({
      id,
      fn,
    }: {
      id: string;
      fn: (id: string) => Promise<CourierAssignmentResponse>;
    }) => fn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courier', 'mine'] });
    },
  });

  const items = query.data ?? [];

  if (query.isLoading) {
    return <div className="text-sm text-muted-foreground">{t('common.loading')}</div>;
  }

  if (query.isError) {
    const message =
      query.error instanceof ApiError && query.error.status === 403
        ? t('courier.errors.forbidden')
        : t('courier.errors.loadFailed');
    return (
      <div className="text-sm text-destructive text-center py-8">
        {message}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        {t('courier.empty.mine')}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-3">
      {items.map((a) => {
        const action = getStatusAction(a.status, t);
        return (
          <AssignmentCard
            key={a.id}
            assignment={a}
            action={
              action ? (
                <Button
                  type="button"
                  className="w-full min-h-12"
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate({ id: a.id, fn: action.mutationFn })}
                >
                  {action.label}
                </Button>
              ) : undefined
            }
          />
        );
      })}
    </div>
  );
}
