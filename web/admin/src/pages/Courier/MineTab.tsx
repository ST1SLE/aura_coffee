import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deliverAssignment,
  listMine,
  pickupAssignment,
  type CourierAssignmentResponse,
  type CourierAssignmentStatus,
} from '@/api/courier';
import { AssignmentCard } from '@/pages/Courier/AssignmentCard';
import { Button } from '@/components/ui/button';

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
