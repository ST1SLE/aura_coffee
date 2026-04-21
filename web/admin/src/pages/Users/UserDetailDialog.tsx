import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  NotificationList,
  useNotifier,
} from '@/components/ui/notifier';
import {
  getUser,
  unblockUser,
  ApiError,
  type UserDetailResponse,
  type LoyaltyTransactionItem,
} from '@/api/admin-users';
import { UserStatusBadge } from './UserStatusBadge';
import { BlockConfirmDialog } from './BlockConfirmDialog';
import { LoyaltyAdjustForm } from './LoyaltyAdjustForm';

interface Props {
  userId: string | null;
  open: boolean;
  onClose: () => void;
  onMutated: () => void;
}

function formatAmount(n: number): string {
  return n > 0 ? `+${n}` : `${n}`;
}

function formatDate(iso: string, locale: string): string {
  try {
    return new Date(iso).toLocaleString(locale);
  } catch {
    return iso;
  }
}

export function UserDetailDialog({ userId, open, onClose, onMutated }: Props) {
  const { t, i18n } = useTranslation();
  const [detail, setDetail] = useState<UserDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [blockOpen, setBlockOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const { notifications, notify, dismiss } = useNotifier();

  async function refetch() {
    if (!userId) return;
    setLoading(true);
    try {
      const d = await getUser(userId);
      setDetail(d);
    } catch {
      notify(t('common.error'), 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open || !userId) {
      setDetail(null);
      setBlockOpen(false);
      setAdjustOpen(false);
      return;
    }
    void refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  async function handleUnblock() {
    if (!userId) return;
    try {
      await unblockUser(userId);
      onMutated();
      await refetch();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        notify(t('common.sessionExpired'), 'error');
      } else {
        notify(t('common.error'), 'error');
      }
    }
  }

  function handleBlockConfirmed() {
    setBlockOpen(false);
    onMutated();
    void refetch();
  }

  async function handleAdjustSuccess() {
    setAdjustOpen(false);
    onMutated();
    await refetch();
  }

  const showBlock = detail?.status === 'active';
  const showUnblock = detail?.status === 'blocked';
  const showAdjust = detail?.status === 'active' || detail?.status === 'blocked';

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('pages.users.detail.title')}</DialogTitle>
          </DialogHeader>

          {loading && !detail && (
            <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
          )}

          {detail && (
            <div className="space-y-4">
              <div
                data-testid="user-detail-header"
                className="flex items-center gap-3"
              >
                <span className="font-medium">{detail.display_name}</span>
                <UserStatusBadge status={detail.status} />
                <span className="text-xs text-muted-foreground">
                  {formatDate(detail.created_at, i18n.language)}
                </span>
              </div>

              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">
                  {t('pages.users.detail.balance')}
                </p>
                <p className="text-2xl font-semibold">
                  {new Intl.NumberFormat(i18n.language).format(detail.loyalty_balance)}{' '}
                  {t('pages.users.balance_unit_short')}
                </p>
              </div>

              <div className="flex gap-2">
                {showBlock && (
                  <Button
                    variant="destructive"
                    data-testid="user-detail-block"
                    onClick={() => setBlockOpen(true)}
                  >
                    {t('pages.users.detail.block_button')}
                  </Button>
                )}
                {showUnblock && (
                  <Button
                    data-testid="user-detail-unblock"
                    onClick={handleUnblock}
                  >
                    {t('pages.users.detail.unblock_button')}
                  </Button>
                )}
                {showAdjust && (
                  <Button
                    variant="outline"
                    data-testid="user-detail-adjust"
                    onClick={() => setAdjustOpen((v) => !v)}
                  >
                    {t('pages.users.detail.adjust_button')}
                  </Button>
                )}
              </div>

              {adjustOpen && userId && (
                <div className="rounded-md border p-3">
                  <LoyaltyAdjustForm
                    userId={userId}
                    onSuccess={handleAdjustSuccess}
                    onNotify={notify}
                  />
                </div>
              )}

              <div className="space-y-2">
                <h4 className="text-sm font-semibold">
                  {t('pages.users.detail.transactions')}
                </h4>
                {detail.loyalty_transactions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t('pages.users.detail.empty_transactions')}
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('pages.users.detail.tx_columns.type')}</TableHead>
                        <TableHead>{t('pages.users.detail.tx_columns.amount')}</TableHead>
                        <TableHead>{t('pages.users.detail.tx_columns.balance_after')}</TableHead>
                        <TableHead>{t('pages.users.detail.tx_columns.description')}</TableHead>
                        <TableHead>{t('pages.users.detail.tx_columns.created_at')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {detail.loyalty_transactions.map((tx: LoyaltyTransactionItem) => (
                        <TableRow key={tx.id} data-testid={`tx-row-${tx.id}`}>
                          <TableCell>
                            {t(`pages.users.detail.tx_type.${tx.type}`)}
                          </TableCell>
                          <TableCell data-testid={`tx-amount-${tx.id}`}>
                            {formatAmount(tx.amount)}
                          </TableCell>
                          <TableCell>{tx.balance_after}</TableCell>
                          <TableCell>{tx.description ?? ''}</TableCell>
                          <TableCell>
                            {formatDate(tx.created_at, i18n.language)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {detail && (
        <BlockConfirmDialog
          open={blockOpen}
          onClose={() => setBlockOpen(false)}
          user={detail}
          onConfirmed={handleBlockConfirmed}
        />
      )}

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </>
  );
}
