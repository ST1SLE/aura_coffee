import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SizeOptionsEditor } from './SizeOptionsEditor';
import { ModifiersPicker } from './ModifiersPicker';
import type { MenuItemResponse, CategoryResponse, ModifierResponse } from '@/api/menu';
import { createItem, updateItem, ApiError } from '@/api/menu';
import { rublesToKopecks, kopecksToRublesStr, pickLang } from './utils';

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
  sort_order: string;
  image_url: string;
  archived: boolean;
}

function makeForm(item?: MenuItemResponse | null): FormState {
  return {
    name_ru: item?.name_ru ?? '',
    name_en: item?.name_en ?? '',
    description_ru: item?.description_ru ?? '',
    description_en: item?.description_en ?? '',
    category_id: item ? String(item.category_id) : '',
    price: item ? kopecksToRublesStr(item.base_price) : '',
    sort_order: item ? String(item.sort_order) : '0',
    image_url: item?.image_url ?? '',
    archived: item?.archived ?? false,
  };
}

export function MenuItemFormDialog({ open, onClose, categories, modifiers, item, onSaved, onError }: Props) {
  const { t, i18n } = useTranslation();

  // После успешного create переходим в режим edit текущего item
  const [editItem, setEditItem] = useState<MenuItemResponse | null>(item ?? null);
  const [form, setForm] = useState<FormState>(() => makeForm(item));
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
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
    if (!form.name_ru.trim()) e.name_ru = t('pages.menu.itemForm.validationNameRu');
    if (!form.name_en.trim()) e.name_en = t('pages.menu.itemForm.validationNameEn');
    if (form.price === '' || parseFloat(form.price) < 0)
      e.price = t('pages.menu.itemForm.validationBasePrice');
    if (!form.category_id) e.category_id = t('pages.menu.itemForm.validationCategory');
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
        sort_order: parseInt(form.sort_order) || 0,
        image_url: form.image_url.trim() || null,
      };

      let saved: MenuItemResponse;
      if (editItem) {
        saved = await updateItem(editItem.id, { ...body, archived: form.archived });
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
        const fields = body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
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
            {isEdit ? t('pages.menu.itemForm.titleEdit') : t('pages.menu.itemForm.titleCreate')}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Название — два языка */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-name-ru">{t('pages.menu.itemForm.nameRu')}</Label>
              <Input
                id="item-name-ru"
                value={form.name_ru}
                onChange={(e) => setForm({ ...form, name_ru: e.target.value })}
                required
              />
              {errors.name_ru && <p className="text-xs text-destructive">{errors.name_ru}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-name-en">{t('pages.menu.itemForm.nameEn')}</Label>
              <Input
                id="item-name-en"
                value={form.name_en}
                onChange={(e) => setForm({ ...form, name_en: e.target.value })}
                required
              />
              {errors.name_en && <p className="text-xs text-destructive">{errors.name_en}</p>}
            </div>
          </div>

          {/* Описание — два языка */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="item-desc-ru">{t('pages.menu.itemForm.descriptionRu')}</Label>
              <Input
                id="item-desc-ru"
                value={form.description_ru}
                onChange={(e) => setForm({ ...form, description_ru: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="item-desc-en">{t('pages.menu.itemForm.descriptionEn')}</Label>
              <Input
                id="item-desc-en"
                value={form.description_en}
                onChange={(e) => setForm({ ...form, description_en: e.target.value })}
              />
            </div>
          </div>

          {/* Категория */}
          <div className="space-y-1">
            <Label htmlFor="item-cat">{t('pages.menu.itemForm.category')}</Label>
            <select
              id="item-cat"
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              required
            >
              <option value="">{t('pages.menu.itemForm.categoryPlaceholder')}</option>
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
            {errors.price && <p className="text-xs text-destructive">{errors.price}</p>}
          </div>

          {/* Порядок сортировки */}
          <div className="space-y-1">
            <Label htmlFor="item-sort">{t('pages.menu.itemForm.sortOrder')}</Label>
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
            <Label htmlFor="item-image">{t('pages.menu.itemForm.imageUrl')}</Label>
            <Input
              id="item-image"
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
          </div>

          {/* Архив — только для edit */}
          {isEdit && (
            <div className="flex items-center gap-2">
              <input
                id="item-archived"
                type="checkbox"
                checked={form.archived}
                onChange={(e) => setForm({ ...form, archived: e.target.checked })}
                className="h-4 w-4"
              />
              <Label htmlFor="item-archived">{t('pages.menu.itemForm.archived')}</Label>
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <Button type="button" variant="outline" onClick={onClose}>
              {t('pages.menu.itemForm.cancel')}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t('pages.menu.itemForm.saving') : t('pages.menu.itemForm.save')}
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
