import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Trash2 } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { MenuItemFormDialog } from './MenuItemFormDialog';
import type { MenuItemResponse, CategoryResponse, Availability } from '@/api/menu';
import { listItems, deleteItem, setItemAvailability, ApiError } from '@/api/menu';
import { formatPrice, pickLang } from './utils';

interface Props {
  categoryId: number | null;
  categories: CategoryResponse[];
  currentRole: 'admin' | 'barista';
  onError: (msg: string) => void;
}

function AvailabilityBadge({ value }: { value: Availability }) {
  const { t } = useTranslation();
  if (value === 'STOP_LIST') {
    return <Badge variant="warning">{t('pages.menu.items.badge.stopList')}</Badge>;
  }
  if (value === 'ARCHIVED') {
    return <Badge variant="muted">{t('pages.menu.items.badge.archived')}</Badge>;
  }
  return null;
}

export function MenuItemsTable({ categoryId, categories, currentRole, onError }: Props) {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<MenuItemResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<MenuItemResponse | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const isAdmin = currentRole === 'admin';

  useEffect(() => {
    setLoading(true);
    listItems(categoryId != null ? { categoryId } : undefined)
      .then(setItems)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
        else onError(t('common.error'));
      })
      .finally(() => setLoading(false));
  }, [categoryId]); // eslint-disable-line react-hooks/exhaustive-deps

  function openCreate() {
    setSelectedItem(null);
    setDialogOpen(true);
  }

  function openEdit(item: MenuItemResponse) {
    setSelectedItem(item);
    setDialogOpen(true);
  }

  async function handleDelete(item: MenuItemResponse) {
    if (!confirm(t('pages.menu.items.deleteConfirm'))) return;
    try {
      await deleteItem(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    }
  }

  async function handleToggleAvailability(item: MenuItemResponse, next: boolean) {
    setTogglingId(item.id);
    try {
      const updated = await setItemAvailability(item.id, next);
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('common.errorToggle'));
    } finally {
      setTogglingId(null);
    }
  }

  function handleSaved(saved: MenuItemResponse) {
    setItems((prev) => {
      const idx = prev.findIndex((i) => i.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [...prev, saved];
    });
  }

  if (loading) return <p className="text-sm text-muted-foreground">{t('common.loading')}</p>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t('pages.menu.items.title')}</h2>
        {isAdmin && (
          <Button size="sm" onClick={openCreate}>
            {t('pages.menu.items.newItem')}
          </Button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('pages.menu.items.empty')}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('pages.menu.items.name')}</TableHead>
              <TableHead>{t('pages.menu.items.price')}</TableHead>
              <TableHead>{t('pages.menu.items.availability')}</TableHead>
              {isAdmin && <TableHead>{t('pages.menu.items.actions')}</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">
                  {pickLang(item.name_ru, item.name_en, i18n.language)}
                </TableCell>
                <TableCell>{formatPrice(item.base_price)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={item.availability === 'AVAILABLE'}
                      disabled={item.availability === 'ARCHIVED' || togglingId === item.id}
                      onCheckedChange={(checked) => handleToggleAvailability(item, checked)}
                    />
                    <AvailabilityBadge value={item.availability} />
                  </div>
                </TableCell>
                {isAdmin && (
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(item)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        onClick={() => handleDelete(item)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <MenuItemFormDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        categories={categories}
        item={selectedItem}
        onSaved={handleSaved}
        onError={onError}
      />
    </div>
  );
}
