import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Infinity as InfinityIcon, Pencil, Save, Trash2 } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { MenuItemFormDialog } from './MenuItemFormDialog';
import type {
  MenuItemResponse,
  CategoryResponse,
  Availability,
  ModifierResponse,
} from '@/api/menu';
import {
  listItems,
  deleteItem,
  setItemAvailability,
  setItemInventory,
  ApiError,
} from '@/api/menu';
import { formatPrice, pickLang } from './utils';

// START_MODULE_CONTRACT
//   PURPOSE: Center-column menu items table — list, toggle availability and
//            finite inventory (admin AND barista), edit and delete (admin only).
//            Owns the MenuItemFormDialog state.
//   SCOPE:   Used only by MenuPage.
//   DEPENDS: react, react-i18next, lucide-react, ui primitives, @/api/menu, ./utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4,
//            INV-002 (item CRUD admin-only server-side; availability/inventory
//            operations allowed for admin+barista — matches stop-list rule from AGENTS.md),
//            INV-010.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuItemsTable - data-fetching items table with availability switch and admin-only CRUD
// END_MODULE_MAP

interface Props {
  categoryId: number | null;
  categories: CategoryResponse[];
  modifiers: ModifierResponse[];
  currentRole: 'admin' | 'barista';
  onError: (msg: string) => void;
}

function AvailabilityBadge({ value }: { value: Availability }) {
  const { t } = useTranslation();
  if (value === 'stop_list') {
    return (
      <Badge variant="warning">{t('pages.menu.items.badge.stopList')}</Badge>
    );
  }
  if (value === 'archived') {
    return (
      <Badge variant="muted">{t('pages.menu.items.badge.archived')}</Badge>
    );
  }
  return null;
}

function InventoryBadge({ quantity }: { quantity: number | null }) {
  const { t } = useTranslation();
  if (quantity == null) {
    return (
      <Badge variant="muted">
        {t('pages.menu.items.inventoryBadge.unlimited')}
      </Badge>
    );
  }
  if (quantity === 0) {
    return (
      <Badge variant="destructive">
        {t('pages.menu.items.inventoryBadge.outOfStock')}
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">
      {t('pages.menu.items.inventoryBadge.finite', { count: quantity })}
    </Badge>
  );
}

function inventoryDraftFromItem(item: MenuItemResponse): string {
  return item.inventory_quantity == null ? '' : String(item.inventory_quantity);
}

function normalizeInventoryQuantityInput(value: string): string {
  if (value.trim() === '') return '';
  const quantity = Number(value);
  if (!Number.isFinite(quantity)) return '';
  return String(Math.max(0, Math.floor(quantity)));
}

function isValidInventoryDraft(value: string): boolean {
  if (value.trim() === '') return false;
  const quantity = Number(value);
  return Number.isInteger(quantity) && quantity >= 0;
}

const mobileLabelClass =
  'text-xs font-medium uppercase tracking-wide text-muted-foreground md:hidden';
const responsiveRowClass =
  'block rounded-lg border bg-card p-3 shadow-sm md:table-row md:rounded-none md:border-b md:p-0 md:shadow-none';
const responsiveCellClass =
  'flex items-center justify-between gap-4 py-2 text-sm md:table-cell md:p-2';

// START_CONTRACT: MenuItemsTable
//   PURPOSE: Fetch items for the selected category, render them as a table,
//            and wire availability, inventory, delete, and edit controls. Opens
//            MenuItemFormDialog for create/edit.
//   INPUTS:  Props { categoryId, categories, modifiers, currentRole, onError }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET listItems (refetch on categoryId change);
//            PATCH setItemAvailability (admin+barista — INV-002);
//            PATCH setItemInventory (admin+barista — INV-002);
//            DELETE deleteItem (admin only — server enforces).
//   LINKS:   INV-002, INV-010 (barista sees only operational item controls).
// END_CONTRACT: MenuItemsTable
export function MenuItemsTable({
  categoryId,
  categories,
  modifiers,
  currentRole,
  onError,
}: Props) {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<MenuItemResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<MenuItemResponse | null>(
    null,
  );
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [savingInventoryId, setSavingInventoryId] = useState<number | null>(
    null,
  );
  const [inventoryDrafts, setInventoryDrafts] = useState<
    Record<number, string>
  >({});
  const isAdmin = currentRole === 'admin';

  useEffect(() => {
    setLoading(true);
    listItems(categoryId != null ? { categoryId } : undefined)
      .then((nextItems) => {
        setItems(nextItems);
        setInventoryDrafts(
          Object.fromEntries(
            nextItems.map((item) => [item.id, inventoryDraftFromItem(item)]),
          ),
        );
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401)
          onError(t('common.sessionExpired'));
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
      if (err instanceof ApiError && err.status === 401)
        onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    }
  }

  async function handleToggleAvailability(
    item: MenuItemResponse,
    next: boolean,
  ) {
    setTogglingId(item.id);
    try {
      const updated = await setItemAvailability(item.id, next);
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      setInventoryDrafts((prev) => ({
        ...prev,
        [updated.id]: inventoryDraftFromItem(updated),
      }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401)
        onError(t('common.sessionExpired'));
      else onError(t('common.errorToggle'));
    } finally {
      setTogglingId(null);
    }
  }

  async function handleSetInventory(
    item: MenuItemResponse,
    quantity: number | null,
  ) {
    setSavingInventoryId(item.id);
    try {
      const updated = await setItemInventory(item.id, quantity);
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      setInventoryDrafts((prev) => ({
        ...prev,
        [updated.id]: inventoryDraftFromItem(updated),
      }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401)
        onError(t('common.sessionExpired'));
      else onError(t('pages.menu.items.errorInventory'));
    } finally {
      setSavingInventoryId(null);
    }
  }

  function handleSaved(saved: MenuItemResponse) {
    setInventoryDrafts((prev) => ({
      ...prev,
      [saved.id]: inventoryDraftFromItem(saved),
    }));
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

  if (loading)
    return (
      <p className="admin-surface-soft p-4 text-sm text-muted-foreground">
        {t('common.loading')}
      </p>
    );

  return (
    <div className="space-y-3">
      <div className="admin-surface-soft flex items-center justify-between gap-3 p-3">
        <h2 className="text-lg font-semibold">{t('pages.menu.items.title')}</h2>
        {isAdmin && (
          <Button size="sm" onClick={openCreate}>
            {t('pages.menu.items.newItem')}
          </Button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="admin-surface p-6 text-sm text-muted-foreground">
          {t('pages.menu.items.empty')}
        </p>
      ) : (
        <Table className="block md:table">
          <TableHeader className="hidden md:table-header-group">
            <TableRow>
              <TableHead>{t('pages.menu.items.name')}</TableHead>
              <TableHead>{t('pages.menu.items.price')}</TableHead>
              <TableHead>{t('pages.menu.items.inventory')}</TableHead>
              <TableHead>{t('pages.menu.items.availability')}</TableHead>
              {isAdmin && (
                <TableHead>{t('pages.menu.items.actions')}</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody className="block space-y-3 md:table-row-group md:space-y-0">
            {items.map((item) => {
              const itemName = pickLang(
                item.name_ru,
                item.name_en,
                i18n.language,
              );
              const inventoryDraft =
                inventoryDrafts[item.id] ?? inventoryDraftFromItem(item);
              const inventoryBusy = savingInventoryId === item.id;
              const inventoryControlsDisabled =
                item.availability === 'archived' || inventoryBusy;
              const inventorySaveDisabled =
                inventoryControlsDisabled ||
                !isValidInventoryDraft(inventoryDraft);

              return (
                <TableRow key={item.id} className={responsiveRowClass}>
                  <TableCell className={responsiveCellClass}>
                    <span className={mobileLabelClass}>
                      {t('pages.menu.items.name')}
                    </span>
                    <span className="font-medium">{itemName}</span>
                  </TableCell>
                  <TableCell className={responsiveCellClass}>
                    <span className={mobileLabelClass}>
                      {t('pages.menu.items.price')}
                    </span>
                    <span>{formatPrice(item.base_price)}</span>
                  </TableCell>
                  <TableCell className="flex items-start justify-between gap-4 py-2 text-sm md:table-cell md:p-2">
                    <span className={mobileLabelClass}>
                      {t('pages.menu.items.inventory')}
                    </span>
                    <div className="flex min-w-0 flex-col items-end gap-2 md:min-w-44 md:items-start">
                      <InventoryBadge quantity={item.inventory_quantity} />
                      <div className="flex items-center gap-1">
                        <Input
                          type="number"
                          min="0"
                          step="1"
                          value={inventoryDraft}
                          onChange={(e) =>
                            setInventoryDrafts((prev) => ({
                              ...prev,
                              [item.id]: normalizeInventoryQuantityInput(
                                e.target.value,
                              ),
                            }))
                          }
                          placeholder={t(
                            'pages.menu.items.inventoryPlaceholder',
                          )}
                          aria-label={t(
                            'pages.menu.items.inventoryQuantityAria',
                            {
                              name: itemName,
                            },
                          )}
                          className="h-8 w-20"
                          disabled={inventoryControlsDisabled}
                        />
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={inventorySaveDisabled}
                          onClick={() =>
                            handleSetInventory(
                              item,
                              parseInt(inventoryDraft, 10),
                            )
                          }
                          aria-label={t('pages.menu.items.inventorySaveAria', {
                            name: itemName,
                          })}
                          title={t('pages.menu.items.inventorySaveAria', {
                            name: itemName,
                          })}
                        >
                          <Save className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={inventoryControlsDisabled}
                          onClick={() => handleSetInventory(item, null)}
                          aria-label={t(
                            'pages.menu.items.inventoryUnlimitedAria',
                            {
                              name: itemName,
                            },
                          )}
                          title={t('pages.menu.items.inventoryUnlimitedAria', {
                            name: itemName,
                          })}
                        >
                          <InfinityIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className={responsiveCellClass}>
                    <span className={mobileLabelClass}>
                      {t('pages.menu.items.availability')}
                    </span>
                    <div className="flex items-center justify-end gap-2 md:justify-start">
                      <Switch
                        checked={item.availability === 'available'}
                        disabled={
                          item.availability === 'archived' ||
                          togglingId === item.id
                        }
                        onCheckedChange={(checked) =>
                          handleToggleAvailability(item, checked)
                        }
                      />
                      <AvailabilityBadge value={item.availability} />
                    </div>
                  </TableCell>
                  {isAdmin && (
                    <TableCell className={responsiveCellClass}>
                      <span className={mobileLabelClass}>
                        {t('pages.menu.items.actions')}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openEdit(item)}
                          aria-label={t('pages.menu.items.editAria', {
                            name: itemName,
                          })}
                          title={t('pages.menu.items.editAria', {
                            name: itemName,
                          })}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive"
                          onClick={() => handleDelete(item)}
                          aria-label={t('pages.menu.items.deleteAria', {
                            name: itemName,
                          })}
                          title={t('pages.menu.items.deleteAria', {
                            name: itemName,
                          })}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <MenuItemFormDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        categories={categories}
        modifiers={modifiers}
        item={selectedItem}
        onSaved={handleSaved}
        onError={onError}
      />
    </div>
  );
}
