import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  listAvailable,
  takeAssignment,
  type CourierAssignmentResponse,
} from '@/api/courier';
import { AssignmentCard } from '@/pages/Courier/AssignmentCard';
import { useCourierNotifier } from '@/pages/Courier/notifier-context';
import { Button } from '@/components/ui/button';

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
    return <div className="text-sm text-muted-foreground">{t('common.loading')}</div>;
  }

  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        {t('courier.empty.available')}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-3">
      {items.map((a) => (
        <AssignmentCard
          key={a.id}
          assignment={a}
          action={
            <Button
              type="button"
              className="w-full min-h-12"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(a.id)}
            >
              {t('courier.actions.take')}
            </Button>
          }
        />
      ))}
    </div>
  );
}
