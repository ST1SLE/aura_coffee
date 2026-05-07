import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SizeOptionsEditor } from './SizeOptionsEditor';
import { ModifiersPicker } from './ModifiersPicker';
import type {
  MenuItemResponse,
  CategoryResponse,
  ModifierResponse,
  MenuMediaType,
} from '@/api/menu';
import { createItem, updateItem, ApiError } from '@/api/menu';
import { rublesToKopecks, kopecksToRublesStr, pickLang } from './utils';

// START_MODULE_CONTRACT
//   PURPOSE: Modal dialog for creating or editing a menu item. After successful
//            create, switches into edit mode so the user can immediately add
//            sizes and modifier links to the new item.
//   SCOPE:   Opened by MenuItemsTable. Admin-only feature on the server side.
//   DEPENDS: react, react-i18next, ui primitives, @/api/menu, sibling SizeOptionsEditor,
//            ModifiersPicker, ./utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4,
//            INV-002 (admin-only server-side; this dialog should not be reachable
//            for barista since MenuItemsTable hides the trigger button).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuItemFormDialog - admin-only create/edit dialog with sizes + modifiers panel
// END_MODULE_MAP

const MEDIA_PATH_PREFIX = '/media/menu/';
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.avif'];
const VIDEO_EXTENSIONS = ['.mp4', '.webm'];

type MediaTypeFormValue = '' | MenuMediaType;
type InventoryMode = 'unlimited' | 'finite';

interface Props {
  open: boolean;
  onClose: () => void;
  categories: CategoryResponse[];
  modifiers: ModifierResponse[];
  item?: MenuItemResponse | null; // null = создание
  onSaved: (item: MenuItemResponse) => void;
  onError: (msg: string) => void;
}

interface FormState {
  name_ru: string;
  name_en: string;
  description_ru: string;
  description_en: string;
  category_id: string;
  price: string;
  inventory_mode: InventoryMode;
  inventory_quantity: string;
  sort_order: string;
  image_url: string;
  media_type: MediaTypeFormValue;
  media_url: string;
  media_poster_url: string;
  archived: boolean;
}

function makeForm(item?: MenuItemResponse | null): FormState {
  const inventoryQuantity = item?.inventory_quantity ?? null;
  return {
    name_ru: item?.name_ru ?? '',
    name_en: item?.name_en ?? '',
    description_ru: item?.description_ru ?? '',
    description_en: item?.description_en ?? '',
    category_id: item ? String(item.category_id) : '',
    price: item ? kopecksToRublesStr(item.base_price) : '',
    inventory_mode: inventoryQuantity == null ? 'unlimited' : 'finite',
    inventory_quantity:
      inventoryQuantity == null ? '' : String(inventoryQuantity),
    sort_order: item ? String(item.sort_order) : '0',
    image_url: item?.image_url ?? '',
    media_type: item?.media_type ?? '',
    media_url: item?.media_url ?? '',
    media_poster_url: item?.media_poster_url ?? '',
    archived: item?.archived ?? false,
  };
}

function isPublicMenuMediaPath(value: string): boolean {
  const path = value.trim();
  return (
    path.startsWith(MEDIA_PATH_PREFIX) &&
    !path.includes('?') &&
    !path.includes('#') &&
    !path.includes('://') &&
    !path.startsWith('//') &&
    !path.split('/').includes('..') &&
    !/\s/.test(path)
  );
}

function hasExtension(value: string, extensions: string[]): boolean {
  const path = value.trim().toLowerCase();
  return extensions.some((extension) => path.endsWith(extension));
}

function normalizeInventoryQuantityInput(value: string): string {
  if (value.trim() === '') return '';
  const quantity = Number(value);
  if (!Number.isFinite(quantity)) return '';
  return String(Math.max(0, Math.floor(quantity)));
}

// START_CONTRACT: MenuItemFormDialog
//   PURPOSE: Render the item form, validate locally, POST/PUT through createItem/
//            updateItem, and on success notify the parent list. After create,
//            transitions into edit mode so size/modifier panels become enabled.
//   INPUTS:  Props { open, onClose, categories, modifiers, item, onSaved, onError }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: POST createItem / PUT updateItem; 422/401 surfaced via onError.
//   LINKS:   INV-002 (admin scope server-enforced).
// END_CONTRACT: MenuItemFormDialog
export function MenuItemFormDialog({
  open,
  onClose,
  categories,
  modifiers,
  item,
  onSaved,
  onError,
}: Props) {
  const { t, i18n } = useTranslation();

  // После успешного create переходим в режим edit текущего item
  const [editItem, setEditItem] = useState<MenuItemResponse | null>(
    item ?? null,
  );
  const [form, setForm] = useState<FormState>(() => makeForm(item));
  const [errors, setErrors] = useState<
    Partial<Record<keyof FormState, string>>
  >({});
  const [saving, setSaving] = useState(false);
  const [sizes, setSizes] = useState(item?.size_options ?? []);
  const [selectedModifierIds, setSelectedModifierIds] = useState<number[]>(
    item?.modifiers.map((m) => m.id) ?? [],
  );

  useEffect(() => {
    if (open) {
      setEditItem(item ?? null);
      setForm(makeForm(item));
      setSizes(item?.size_options ?? []);
      setSelectedModifierIds(item?.modifiers.map((m) => m.id) ?? []);
      setErrors({});
    }
  }, [open, item]);

  function validate(): boolean {
    const e: typeof errors = {};
    if (!form.name_ru.trim())
      e.name_ru = t('pages.menu.itemForm.validationNameRu');
    if (!form.name_en.trim())
      e.name_en = t('pages.menu.itemForm.validationNameEn');
    if (form.price === '' || parseFloat(form.price) < 0)
      e.price = t('pages.menu.itemForm.validationBasePrice');
    if (form.inventory_mode === 'finite') {
      const inventoryQuantity = Number(form.inventory_quantity);
      if (
        form.inventory_quantity === '' ||
        !Number.isInteger(inventoryQuantity) ||
        inventoryQuantity < 0
      ) {
        e.inventory_quantity = t(
          'pages.menu.itemForm.validationInventoryQuantity',
        );
      }
    }
    if (!form.category_id)
      e.category_id = t('pages.menu.itemForm.validationCategory');
    const mediaUrl = form.media_url.trim();
    const mediaPosterUrl = form.media_poster_url.trim();
    if (!form.media_type) {
      if (mediaUrl || mediaPosterUrl) {
        e.media_type = t('pages.menu.itemForm.validationMediaType');
      }
    } else {
      if (!mediaUrl) {
        e.media_url = t('pages.menu.itemForm.validationMediaUrlRequired');
      } else if (!isPublicMenuMediaPath(mediaUrl)) {
        e.media_url = t('pages.menu.itemForm.validationMediaPath');
      } else if (
        form.media_type === 'video' &&
        !hasExtension(mediaUrl, VIDEO_EXTENSIONS)
      ) {
        e.media_url = t('pages.menu.itemForm.validationVideoPath');
      } else if (
        form.media_type === 'image' &&
        !hasExtension(mediaUrl, IMAGE_EXTENSIONS)
      ) {
        e.media_url = t('pages.menu.itemForm.validationImagePath');
      }

      if (form.media_type === 'video') {
        if (!mediaPosterUrl) {
          e.media_poster_url = t(
            'pages.menu.itemForm.validationPosterRequired',
          );
        } else if (!isPublicMenuMediaPath(mediaPosterUrl)) {
          e.media_poster_url = t('pages.menu.itemForm.validationMediaPath');
        } else if (!hasExtension(mediaPosterUrl, IMAGE_EXTENSIONS)) {
          e.media_poster_url = t('pages.menu.itemForm.validationPosterPath');
        }
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const body = {
        name_ru: form.name_ru.trim(),
        name_en: form.name_en.trim(),
        description_ru: form.description_ru.trim() || null,
        description_en: form.description_en.trim() || null,
        category_id: parseInt(form.category_id),
        base_price: rublesToKopecks(form.price),
        inventory_quantity:
          form.inventory_mode === 'finite'
            ? parseInt(form.inventory_quantity, 10)
            : null,
        sort_order: parseInt(form.sort_order) || 0,
        image_url: form.image_url.trim() || null,
        media_type: form.media_type || null,
        media_url: form.media_type ? form.media_url.trim() || null : null,
        media_poster_url:
          form.media_type === 'video'
            ? form.media_poster_url.trim() || null
            : null,
      };

      let saved: MenuItemResponse;
      if (editItem) {
        saved = await updateItem(editItem.id, {
          ...body,
          archived: form.archived,
        });
      } else {
        saved = await createItem(body);
        // после создания переходим в edit-режим чтобы можно было добавлять размеры
        setEditItem(saved);
        setSizes(saved.size_options);
        setForm(makeForm(saved));
      }
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { detail?: Array<{ loc: string[] }> } | null;
        const fields =
          body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
        onError(t('pages.menu.itemForm.error422', { fields }));
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('pages.menu.itemForm.errorGeneric'));
      }
    } finally {
      setSaving(false);
    }
  }

  const isEdit = editItem != null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit
              ? t('pages.menu.itemForm.titleEdit')
              : t('pages.menu.itemForm.titleCreate')}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t('pages.menu.itemForm.dialogDescription')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Название — два языка */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-name-ru">
                {t('pages.menu.itemForm.nameRu')}
              </Label>
              <Input
                id="item-name-ru"
                value={form.name_ru}
                onChange={(e) => setForm({ ...form, name_ru: e.target.value })}
                required
              />
              {errors.name_ru && (
                <p className="text-xs text-destructive">{errors.name_ru}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-name-en">
                {t('pages.menu.itemForm.nameEn')}
              </Label>
              <Input
                id="item-name-en"
                value={form.name_en}
                onChange={(e) => setForm({ ...form, name_en: e.target.value })}
                required
              />
              {errors.name_en && (
                <p className="text-xs text-destructive">{errors.name_en}</p>
              )}
            </div>
          </div>

          {/* Описание — два языка */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-desc-ru">
                {t('pages.menu.itemForm.descriptionRu')}
              </Label>
              <Input
                id="item-desc-ru"
                value={form.description_ru}
                onChange={(e) =>
                  setForm({ ...form, description_ru: e.target.value })
                }
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-desc-en">
                {t('pages.menu.itemForm.descriptionEn')}
              </Label>
              <Input
                id="item-desc-en"
                value={form.description_en}
                onChange={(e) =>
                  setForm({ ...form, description_en: e.target.value })
                }
              />
            </div>
          </div>

          {/* Категория */}
          <div className="space-y-1">
            <Label htmlFor="item-cat">
              {t('pages.menu.itemForm.category')}
            </Label>
            <select
              id="item-cat"
              value={form.category_id}
              onChange={(e) =>
                setForm({ ...form, category_id: e.target.value })
              }
              className="flex h-9 w-full rounded-md border border-input bg-[hsl(var(--field))] px-3 py-1 text-sm shadow-sm focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
              required
            >
              <option value="">
                {t('pages.menu.itemForm.categoryPlaceholder')}
              </option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {pickLang(c.name_ru, c.name_en, i18n.language)}
                </option>
              ))}
            </select>
            {errors.category_id && (
              <p className="text-xs text-destructive">{errors.category_id}</p>
            )}
          </div>

          {/* Цена */}
          <div className="space-y-1">
            <Label htmlFor="item-price">{t('pages.menu.itemForm.price')}</Label>
            <Input
              id="item-price"
              type="number"
              step="0.01"
              min="0"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              placeholder={t('pages.menu.itemForm.pricePlaceholder')}
              required
            />
            {errors.price && (
              <p className="text-xs text-destructive">{errors.price}</p>
            )}
          </div>

          {/* Остатки */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-inventory-mode">
                {t('pages.menu.itemForm.inventoryMode')}
              </Label>
              <select
                id="item-inventory-mode"
                value={form.inventory_mode}
                onChange={(e) => {
                  const inventoryMode = e.target.value as InventoryMode;
                  setForm((prev) => ({
                    ...prev,
                    inventory_mode: inventoryMode,
                    inventory_quantity:
                      inventoryMode === 'finite'
                        ? prev.inventory_quantity || '0'
                        : '',
                  }));
                }}
                className="flex h-9 w-full rounded-md border border-input bg-[hsl(var(--field))] px-3 py-1 text-sm shadow-sm focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
              >
                <option value="unlimited">
                  {t('pages.menu.itemForm.inventoryUnlimited')}
                </option>
                <option value="finite">
                  {t('pages.menu.itemForm.inventoryFinite')}
                </option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-inventory-quantity">
                {t('pages.menu.itemForm.inventoryQuantity')}
              </Label>
              <Input
                id="item-inventory-quantity"
                type="number"
                min="0"
                step="1"
                value={form.inventory_quantity}
                onChange={(e) =>
                  setForm({
                    ...form,
                    inventory_quantity: normalizeInventoryQuantityInput(
                      e.target.value,
                    ),
                  })
                }
                disabled={form.inventory_mode === 'unlimited'}
              />
              {errors.inventory_quantity && (
                <p className="text-xs text-destructive">
                  {errors.inventory_quantity}
                </p>
              )}
            </div>
          </div>

          {/* Порядок сортировки */}
          <div className="space-y-1">
            <Label htmlFor="item-sort">
              {t('pages.menu.itemForm.sortOrder')}
            </Label>
            <Input
              id="item-sort"
              type="number"
              min="0"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
            />
          </div>

          {/* URL изображения */}
          <div className="space-y-1">
            <Label htmlFor="item-image">
              {t('pages.menu.itemForm.imageUrl')}
            </Label>
            <Input
              id="item-image"
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
          </div>

          {/* Презентационные медиа */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-media-type">
                {t('pages.menu.itemForm.mediaType')}
              </Label>
              <select
                id="item-media-type"
                value={form.media_type}
                onChange={(e) => {
                  const mediaType = e.target.value as MediaTypeFormValue;
                  setForm((prev) => ({
                    ...prev,
                    media_type: mediaType,
                    media_url: mediaType ? prev.media_url : '',
                    media_poster_url:
                      mediaType === 'video' ? prev.media_poster_url : '',
                  }));
                }}
                className="flex h-9 w-full rounded-md border border-input bg-[hsl(var(--field))] px-3 py-1 text-sm shadow-sm focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
              >
                <option value="">
                  {t('pages.menu.itemForm.mediaTypeNone')}
                </option>
                <option value="image">
                  {t('pages.menu.itemForm.mediaTypeImage')}
                </option>
                <option value="video">
                  {t('pages.menu.itemForm.mediaTypeVideo')}
                </option>
              </select>
              {errors.media_type && (
                <p className="text-xs text-destructive">{errors.media_type}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-media-url">
                {form.media_type === 'video'
                  ? t('pages.menu.itemForm.videoPath')
                  : t('pages.menu.itemForm.mediaUrl')}
              </Label>
              <Input
                id="item-media-url"
                value={form.media_url}
                onChange={(e) =>
                  setForm({ ...form, media_url: e.target.value })
                }
                placeholder="/media/menu/latte/hero.mp4"
                disabled={!form.media_type}
              />
              {errors.media_url && (
                <p className="text-xs text-destructive">{errors.media_url}</p>
              )}
            </div>
          </div>

          {form.media_type === 'video' && (
            <div className="space-y-1">
              <Label htmlFor="item-media-poster">
                {t('pages.menu.itemForm.mediaPosterUrl')}
              </Label>
              <Input
                id="item-media-poster"
                value={form.media_poster_url}
                onChange={(e) =>
                  setForm({ ...form, media_poster_url: e.target.value })
                }
                placeholder="/media/menu/latte/poster.webp"
              />
              {errors.media_poster_url && (
                <p className="text-xs text-destructive">
                  {errors.media_poster_url}
                </p>
              )}
            </div>
          )}

          {/* Архив — только для edit */}
          {isEdit && (
            <div className="flex items-center gap-2">
              <input
                id="item-archived"
                type="checkbox"
                checked={form.archived}
                onChange={(e) =>
                  setForm({ ...form, archived: e.target.checked })
                }
                className="h-4 w-4"
              />
              <Label htmlFor="item-archived">
                {t('pages.menu.itemForm.archived')}
              </Label>
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <Button type="button" variant="outline" onClick={onClose}>
              {t('pages.menu.itemForm.cancel')}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving
                ? t('pages.menu.itemForm.saving')
                : t('pages.menu.itemForm.save')}
            </Button>
          </div>
        </form>

        {/* Размеры — только когда item уже сохранён */}
        <div className="border-t pt-4">
          <SizeOptionsEditor
            menuItemId={editItem?.id ?? 0}
            sizes={sizes}
            onChange={setSizes}
            disabled={!isEdit}
            onError={onError}
          />
        </div>

        {/* Модификаторы — только когда item уже сохранён */}
        <div className="border-t pt-4">
          <ModifiersPicker
            menuItemId={editItem?.id ?? 0}
            allModifiers={modifiers}
            selectedIds={selectedModifierIds}
            onChange={(next) => {
              setSelectedModifierIds(next);
              if (editItem) {
                onSaved({
                  ...editItem,
                  modifiers: modifiers.filter((m) => next.includes(m.id)),
                });
              }
            }}
            disabled={!isEdit}
            onError={onError}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
