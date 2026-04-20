import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import {
  listPromocodes,
  activatePromocode,
  deactivatePromocode,
  parseFieldErrors,
  ApiError,
} from '@/api/promocodes';
import type {
  PromocodeResponse,
  PromocodeStateFilter,
} from '@/api/promocodes';
import { PromosTable } from './PromosTable';
import { PromoFormDialog } from './PromoFormDialog';

const STATE_FILTERS: PromocodeStateFilter[] = [
  'all',
  'active',
  'inactive',
  'expired',
  'exhausted',
];

const DEFAULT_PER_PAGE = 20;
const SEARCH_DEBOUNCE_MS = 300;

export function PromosPage() {
  const { t } = useTranslation();
  const { notifications, notify, dismiss } = useNotifier();

  const [stateFilter, setStateFilter] = useState<PromocodeStateFilter>('all');
  const [code, setCode] = useState('');
  const [codeDebounced, setCodeDebounced] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<PromocodeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPromo, setEditingPromo] = useState<PromocodeResponse | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  // 300ms debounce для search — один in-flight запрос на финальный ввод.
  useEffect(() => {
    const handle = setTimeout(() => setCodeDebounced(code), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [code]);

  // Сбрасываем page на 1 при смене фильтра.
  useEffect(() => {
    setPage(1);
  }, [stateFilter, codeDebounced]);

  const reloadKey = useMemo(
    () => `${stateFilter}|${codeDebounced}|${page}`,
    [stateFilter, codeDebounced, page],
  );

  async function reload() {
    setLoading(true);
    try {
      const res = await listPromocodes({
        state: stateFilter,
        code: codeDebounced || undefined,
        page,
        per_page: DEFAULT_PER_PAGE,
      });
      setItems(res.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        notify(t('common.sessionExpired'), 'error');
      } else {
        notify(t('common.error'), 'error');
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  function openCreate() {
    setEditingPromo(null);
    setDialogOpen(true);
  }

  function openEdit(promo: PromocodeResponse) {
    setEditingPromo(promo);
    setDialogOpen(true);
  }

  function handleSaved(saved: PromocodeResponse) {
    setItems((prev) => {
      const idx = prev.findIndex((p) => p.id === saved.id);
      if (idx === -1) return [saved, ...prev];
      const next = [...prev];
      next[idx] = saved;
      return next;
    });
    setDialogOpen(false);
    setEditingPromo(null);
    // После create/update перезагружаем список, чтобы получить свежий state/order.
    reload();
  }

  async function handleActivate(promo: PromocodeResponse) {
    setPendingId(promo.id);
    try {
      const saved = await activatePromocode(promo.id);
      setItems((prev) => prev.map((p) => (p.id === saved.id ? saved : p)));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const body = err.body as { detail?: string } | null;
        notify(body?.detail ?? t('common.error'), 'error');
      } else if (err instanceof ApiError && err.status === 422) {
        const fe = parseFieldErrors(err);
        notify(Object.values(fe).join('; ') || t('common.error'), 'error');
      } else {
        notify(t('common.error'), 'error');
      }
    } finally {
      setPendingId(null);
    }
  }

  async function handleDeactivate(promo: PromocodeResponse) {
    setPendingId(promo.id);
    try {
      const saved = await deactivatePromocode(promo.id);
      setItems((prev) => prev.map((p) => (p.id === saved.id ? saved : p)));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        notify(t('pages.promos.errors.activate_expired'), 'error');
      } else {
        notify(t('common.error'), 'error');
      }
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold">{t('pages.promos.title')}</h1>
        <Button onClick={openCreate}>{t('pages.promos.actions.create')}</Button>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist">
        {STATE_FILTERS.map((s) => (
          <Button
            key={s}
            role="tab"
            variant={stateFilter === s ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStateFilter(s)}
            data-testid={`state-tab-${s}`}
            aria-selected={stateFilter === s}
          >
            {t(`pages.promos.state.${s}`)}
          </Button>
        ))}
      </div>

      <div className="max-w-sm">
        <Input
          type="search"
          placeholder={t('pages.promos.search_placeholder')}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          data-testid="promos-search"
        />
      </div>

      {loading && items.length === 0 ? (
        <p className="text-muted-foreground text-sm py-8 text-center">{t('common.loading')}</p>
      ) : (
        <PromosTable
          items={items}
          onRowClick={openEdit}
          onActivate={handleActivate}
          onDeactivate={handleDeactivate}
          pendingId={pendingId}
          emptyLabel={t('pages.promos.empty')}
        />
      )}

      <PromoFormDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditingPromo(null);
        }}
        promo={editingPromo}
        onSaved={handleSaved}
        onError={(msg) => notify(msg, 'error')}
      />

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
