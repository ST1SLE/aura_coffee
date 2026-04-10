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
import type { MenuItemResponse, CategoryResponse } from '@/api/menu';
import { createItem, updateItem, ApiError } from '@/api/menu';
import { rublesToKopecks, kopecksToRublesStr } from './utils';

interface Props {
  open: boolean;
  onClose: () => void;
  categories: CategoryResponse[];
  item?: MenuItemResponse | null; // null = создание
  onSaved: (item: MenuItemResponse) => void;
  onError: (msg: string) => void;
}

interface FormState {
  name: string;
  description: string;
  category_id: string;
  price: string;
  archived: boolean;
}

function makeForm(item?: MenuItemResponse | null): FormState {
  return {
    name: item?.name ?? '',
    description: item?.description ?? '',
    category_id: item ? String(item.category_id) : '',
    price: item ? kopecksToRublesStr(item.price_kopecks) : '',
    archived: item?.archived ?? false,
  };
}

export function MenuItemFormDialog({ open, onClose, categories, item, onSaved, onError }: Props) {
  const { t } = useTranslation();

  // После успешного create переходим в режим edit текущего item
  const [editItem, setEditItem] = useState<MenuItemResponse | null>(item ?? null);
  const [form, setForm] = useState<FormState>(() => makeForm(item));
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [saving, setSaving] = useState(false);
  const [sizes, setSizes] = useState(item?.size_options ?? []);

  useEffect(() => {
    if (open) {
      setEditItem(item ?? null);
      setForm(makeForm(item));
      setSizes(item?.size_options ?? []);
      setErrors({});
    }
  }, [open, item]);

  function validate(): boolean {
    const e: typeof errors = {};
    if (!form.name.trim()) e.name = t('pages.menu.itemForm.validationName');
    if (form.price === '' || parseFloat(form.price) < 0)
      e.price = t('pages.menu.itemForm.validationPrice');
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
        name: form.name.trim(),
        description: form.description.trim() || null,
        category_id: parseInt(form.category_id),
        price_kopecks: rublesToKopecks(form.price),
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
          {/* Название */}
          <div className="space-y-1">
            <Label htmlFor="item-name">{t('pages.menu.itemForm.name')}</Label>
            <Input
              id="item-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('pages.menu.itemForm.namePlaceholder')}
              required
            />
            {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
          </div>

          {/* Описание */}
          <div className="space-y-1">
            <Label htmlFor="item-desc">{t('pages.menu.itemForm.description')}</Label>
            <Input
              id="item-desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder={t('pages.menu.itemForm.descriptionPlaceholder')}
            />
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
                  {c.name}
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
      </DialogContent>
    </Dialog>
  );
}
