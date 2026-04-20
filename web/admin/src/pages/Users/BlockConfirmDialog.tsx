import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  blockUser,
  type UserDetailResponse,
  type BlockUserResponse,
} from '@/api/admin-users';

interface Props {
  open: boolean;
  onClose: () => void;
  user: UserDetailResponse;
  onConfirmed: (res: BlockUserResponse) => void;
}

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'done'; res: BlockUserResponse };

export function BlockConfirmDialog({ open, onClose, user, onConfirmed }: Props) {
  const { t } = useTranslation();
  const [checked, setChecked] = useState(false);
  const [state, setState] = useState<State>({ kind: 'idle' });

  async function handleConfirm() {
    setState({ kind: 'loading' });
    try {
      const res = await blockUser(user.id);
      setState({ kind: 'done', res });
      onConfirmed(res);
    } catch {
      // Ошибки блокировки показываются парентом через notifier; сбрасываем state.
      setState({ kind: 'idle' });
    }
  }

  function handleClose() {
    setChecked(false);
    setState({ kind: 'idle' });
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('pages.users.block_confirm.title')}</DialogTitle>
          <DialogDescription
            data-testid="block-confirm-warning"
            className="text-destructive"
          >
            {t('pages.users.block_confirm.warning', {
              count: user.active_orders_count,
            })}
          </DialogDescription>
        </DialogHeader>

        {state.kind === 'done' ? (
          <div className="space-y-4">
            <p data-testid="block-confirm-result" className="text-sm">
              {t('pages.users.block_confirm.result', {
                count: state.res.cancelled_orders_count,
              })}
            </p>
            <div className="flex justify-end">
              <Button onClick={handleClose}>
                {t('pages.users.block_confirm.close')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                data-testid="block-confirm-checkbox"
                checked={checked}
                onChange={(e) => setChecked(e.target.checked)}
                className="mt-1"
              />
              <span>{t('pages.users.block_confirm.checkbox')}</span>
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleClose}>
                {t('pages.users.block_confirm.cancel')}
              </Button>
              <Button
                variant="destructive"
                data-testid="block-confirm-submit"
                disabled={!checked || state.kind === 'loading'}
                onClick={handleConfirm}
              >
                {t('pages.users.block_confirm.confirm')}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
