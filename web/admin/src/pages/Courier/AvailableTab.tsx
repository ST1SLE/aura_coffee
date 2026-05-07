import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PackageCheck } from 'lucide-react';
import {
  ApiError,
  listAvailable,
  takeAssignment,
  type CourierAssignmentResponse,
} from '@/api/courier';
import { AssignmentCard } from '@/pages/Courier/AssignmentCard';
import { useCourierNotifier } from '@/pages/Courier/notifier-context';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Tab listing assignments awaiting a courier — polls every 5s and
//            offers a Take action that races against other couriers; on 409
//            shows a toast and refetches.
//   SCOPE:   Used only by CourierPage.
//   DEPENDS: react-i18next, @tanstack/react-query, @/api/courier,
//            ./AssignmentCard, ./notifier-context, ui Button.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (5s real-time),
//            INV-002 (server gates courier scope), INV-010 (no PII beyond address),
//            INV-016 (take is COURIER_ASSIGNED transition).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AvailableTab - polled list of takeable assignments with mutation handler
// END_MODULE_MAP

// START_CONTRACT: AvailableTab
//   PURPOSE: Poll listAvailable every 5s while the document is visible; render
//            cards with a Take button that POSTs takeAssignment, invalidating
//            both 'available' and 'mine' queries on success.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET listAvailable; POST takeAssignment; query invalidation;
//            409 routed to courier notifier.
//   LINKS:   INV-002, INV-010, INV-016.
// END_CONTRACT: AvailableTab
export function AvailableTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { notify } = useCourierNotifier();

  const query = useQuery<CourierAssignmentResponse[]>({
    queryKey: ['courier', 'available'],
    queryFn: listAvailable,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const mutation = useMutation({
    mutationFn: (id: string) => takeAssignment(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courier', 'available'] });
      qc.invalidateQueries({ queryKey: ['courier', 'mine'] });
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        notify(t('courier.errors.alreadyTaken'), 'error');
        qc.invalidateQueries({ queryKey: ['courier', 'available'] });
      }
    },
  });

  const items = query.data ?? [];

  if (query.isLoading) {
    return (
      <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
    );
  }

  if (query.isError) {
    const message =
      query.error instanceof ApiError && query.error.status === 403
        ? t('courier.errors.forbidden')
        : t('courier.errors.loadFailed');
    return (
      <div className="text-sm text-destructive text-center py-8">{message}</div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        {t('courier.empty.available')}
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((a) => (
        <AssignmentCard
          key={a.id}
          assignment={a}
          showAddress={false}
          action={
            <Button
              type="button"
              className="w-full min-h-12"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(a.id)}
            >
              <PackageCheck aria-hidden="true" />
              {t('courier.actions.take')}
            </Button>
          }
        />
      ))}
    </div>
  );
}
