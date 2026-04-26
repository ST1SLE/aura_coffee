import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import {
  listUsers,
  ApiError,
  type UserSummary,
  type UserStatusFilter,
} from '@/api/admin-users';
import { UsersTable } from './UsersTable';
import { UserDetailDialog } from './UserDetailDialog';

// START_MODULE_CONTRACT
//   PURPOSE: Admin user-management page — status tabs, debounced search,
//            paginated list, and a detail dialog with block/unblock and
//            loyalty adjust actions.
//   SCOPE:   Admin-only route (gated by ProtectedRoute and INV-002).
//   DEPENDS: react, react-i18next, ui primitives, @/api/admin-users,
//            sibling UsersTable + UserDetailDialog.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.7,
//            INV-002 (admin scope), INV-013 (PII handling — display_name only,
//            no raw phones in the list).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersPage - data-fetching admin users page with filter/search/pagination
// END_MODULE_MAP

const STATUS_TABS: { key: UserStatusFilter; labelKey: string }[] = [
  { key: 'all', labelKey: 'pages.users.filters.status.all' },
  { key: 'active', labelKey: 'pages.users.filters.status.active' },
  { key: 'blocked', labelKey: 'pages.users.filters.status.blocked' },
  { key: 'pending_verification', labelKey: 'pages.users.filters.status.pending' },
];

const DEFAULT_PER_PAGE = 20;
const SEARCH_DEBOUNCE_MS = 300;

// START_CONTRACT: UsersPage
//   PURPOSE: Compose the user-management UI — status filter tabs, 300ms-debounced
//            search box, paginated list, detail dialog with mutation hooks. Reload
//            cycles on any filter/page/search change.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET listUsers; notifier toasts; child detail dialog triggers
//            blockUser/unblockUser/adjustLoyalty (admin-only server-side).
//   LINKS:   INV-002, INV-013.
// END_CONTRACT: UsersPage
export function UsersPage() {
  const { t } = useTranslation();
  const { notifications, notify, dismiss } = useNotifier();

  const [status, setStatus] = useState<UserStatusFilter>('all');
  const [search, setSearch] = useState('');
  const [searchDebounced, setSearchDebounced] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<UserSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    const handle = setTimeout(() => setSearchDebounced(search), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [status, searchDebounced]);

  const reloadKey = useMemo(
    () => `${status}|${searchDebounced}|${page}`,
    [status, searchDebounced, page],
  );

  async function reload() {
    setLoading(true);
    try {
      const res = await listUsers({
        status,
        search: searchDebounced ? searchDebounced : undefined,
        page,
        perPage: DEFAULT_PER_PAGE,
      });
      setItems(res.items);
      setTotal(res.total);
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

  function handleSelect(id: string) {
    setSelectedId(id);
    setDetailOpen(true);
  }

  function handleDetailClose() {
    setDetailOpen(false);
    setSelectedId(null);
  }

  const maxPage = Math.max(1, Math.ceil(total / DEFAULT_PER_PAGE));
  const canPrev = page > 1;
  const canNext = page < maxPage;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('pages.users.title')}</h1>
        <p className="text-sm text-muted-foreground">
          {t('pages.users.description')}
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist">
        {STATUS_TABS.map((tab) => (
          <Button
            key={tab.key}
            role="tab"
            variant={status === tab.key ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatus(tab.key)}
            data-testid={`users-tab-${tab.key === 'pending_verification' ? 'pending' : tab.key}`}
            aria-selected={status === tab.key}
          >
            {t(tab.labelKey)}
          </Button>
        ))}
      </div>

      <div className="max-w-sm">
        <Input
          type="search"
          placeholder={t('pages.users.search.placeholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="users-search"
        />
      </div>

      {loading && items.length === 0 ? (
        <p className="text-muted-foreground text-sm py-8 text-center">
          {t('common.loading')}
        </p>
      ) : (
        <UsersTable
          items={items}
          onSelect={handleSelect}
          emptyLabel={t('pages.users.empty')}
        />
      )}

      {items.length > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {page} / {maxPage}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!canPrev}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              data-testid="users-prev"
            >
              ‹
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!canNext}
              onClick={() => setPage((p) => p + 1)}
              data-testid="users-next"
            >
              ›
            </Button>
          </div>
        </div>
      )}

      <UserDetailDialog
        userId={selectedId}
        open={detailOpen}
        onClose={handleDetailClose}
        onMutated={reload}
      />

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
