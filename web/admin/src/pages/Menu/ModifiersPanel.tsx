import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { ModifierResponse } from '@/api/menu';
import {
  createModifier,
  updateModifier,
  deleteModifier,
  setModifierAvailability,
  ApiError,
} from '@/api/menu';
import { kopecksToRublesStr, rublesToKopecks, pickLang } from './utils';

// START_MODULE_CONTRACT
//   PURPOSE: Bottom panel on the menu page — list of modifiers with availability
//            toggle (admin OR barista — stop-list) and admin-only create/edit/delete.
//   SCOPE:   Used only by MenuPage.
//   DEPENDS: react, react-i18next, lucide-react, ui primitives, @/api/menu, ./utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4,
//            INV-002 (CRUD admin-only; availability toggle admin+barista),
//            INV-010.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ModifiersPanel - modifiers list with role-gated CRUD and stop-list switch
// END_MODULE_MAP

interface Props {
  modifiers: ModifierResponse[];
  onModifiersChange: (next: ModifierResponse[]) => void;
  currentRole: 'admin' | 'barista';
  onError: (msg: string) => void;
}

interface FormRow {
  name_ru: string;
  name_en: string;
  price: string;
}

const emptyForm = (): FormRow => ({ name_ru: '', name_en: '', price: '' });

// START_CONTRACT: ModifiersPanel
//   PURPOSE: Render the modifier table; expose admin-only create/edit/delete and
//            shared availability toggle. The full list is owned by MenuPage to
//            stay in sync with ModifiersPicker selectors.
//   INPUTS:  Props { modifiers, onModifiersChange, currentRole, onError }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: createModifier/updateModifier/deleteModifier/setModifierAvailability;
//            401/422 routed to onError.
//   LINKS:   INV-002 (server enforces; client filters CRUD UI for barista),
//            INV-010.
// END_CONTRACT: ModifiersPanel
export function ModifiersPanel({
  modifiers,
  onModifiersChange,
  currentRole,
  onError,
}: Props) {
  const { t, i18n } = useTranslation();
  const [addForm, setAddForm] = useState<FormRow>(emptyForm());
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormRow>(emptyForm());
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const isAdmin = currentRole === 'admin';

  async function handleAdd() {
    if (!addForm.name_ru.trim() || !addForm.name_en.trim()) return;
    setAdding(true);
    try {
      const created = await createModifier({
        name_ru: addForm.name_ru.trim(),
        name_en: addForm.name_en.trim(),
        price: rublesToKopecks(addForm.price),
        sort_order: 0,
      });
      onModifiersChange([...modifiers, created]);
      setAddForm(emptyForm());
      setShowAdd(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { detail?: Array<{ loc: string[] }> } | null;
        const fields =
          body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
        onError(t('pages.menu.itemForm.error422', { fields }));
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('pages.menu.modifiers.errorGeneric'));
      }
    } finally {
      setAdding(false);
    }
  }

  function startEdit(m: ModifierResponse) {
    setEditId(m.id);
    setEditForm({
      name_ru: m.name_ru,
      name_en: m.name_en,
      price: kopecksToRublesStr(m.price),
    });
  }

  async function handleSaveEdit(m: ModifierResponse) {
    try {
      const updated = await updateModifier(m.id, {
        name_ru: editForm.name_ru.trim() || m.name_ru,
        name_en: editForm.name_en.trim() || m.name_en,
        price: rublesToKopecks(editForm.price),
      });
      onModifiersChange(modifiers.map((x) => (x.id === m.id ? updated : x)));
      setEditId(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { detail?: Array<{ loc: string[] }> } | null;
        const fields =
          body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
        onError(t('pages.menu.itemForm.error422', { fields }));
      } else {
        onError(t('pages.menu.modifiers.errorGeneric'));
      }
    }
  }

  async function handleDelete(m: ModifierResponse) {
    if (!confirm(t('pages.menu.modifiers.deleteConfirm'))) return;
    try {
      await deleteModifier(m.id);
      onModifiersChange(modifiers.filter((x) => x.id !== m.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401)
        onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    }
  }

  async function handleToggle(m: ModifierResponse, next: boolean) {
    setTogglingId(m.id);
    try {
      const updated = await setModifierAvailability(m.id, next);
      onModifiersChange(modifiers.map((x) => (x.id === m.id ? updated : x)));
    } catch {
      onError(t('pages.menu.modifiers.errorToggle'));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">
          {t('pages.menu.modifiers.title')}
        </h2>
        {isAdmin && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowAdd((v) => !v)}
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('pages.menu.modifiers.newModifier')}
          </Button>
        )}
      </div>

      {/* Форма добавления */}
      {isAdmin && showAdd && (
        <div className="flex flex-col gap-2 rounded-md border border-border/70 bg-[hsl(var(--field))] p-3 shadow-sm md:flex-row md:items-end">
          <div className="w-full space-y-1 md:flex-1">
            <Label htmlFor="mod-name-ru">
              {t('pages.menu.modifiers.nameRu')}
            </Label>
            <Input
              id="mod-name-ru"
              value={addForm.name_ru}
              onChange={(e) =>
                setAddForm({ ...addForm, name_ru: e.target.value })
              }
            />
          </div>
          <div className="w-full space-y-1 md:flex-1">
            <Label htmlFor="mod-name-en">
              {t('pages.menu.modifiers.nameEn')}
            </Label>
            <Input
              id="mod-name-en"
              value={addForm.name_en}
              onChange={(e) =>
                setAddForm({ ...addForm, name_en: e.target.value })
              }
            />
          </div>
          <div className="w-full space-y-1 md:w-28">
            <Label htmlFor="mod-price">{t('pages.menu.modifiers.price')}</Label>
            <Input
              id="mod-price"
              type="number"
              step="0.01"
              value={addForm.price}
              onChange={(e) =>
                setAddForm({ ...addForm, price: e.target.value })
              }
              placeholder="0.00"
            />
          </div>
          <Button
            className="w-full md:w-auto"
            disabled={adding}
            onClick={handleAdd}
          >
            {adding
              ? t('pages.menu.modifiers.saving')
              : t('pages.menu.modifiers.save')}
          </Button>
          <Button
            variant="ghost"
            className="w-full md:w-auto"
            onClick={() => setShowAdd(false)}
          >
            {t('pages.menu.modifiers.cancel')}
          </Button>
        </div>
      )}

      {modifiers.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t('pages.menu.modifiers.empty')}
        </p>
      )}

      <ul className="space-y-2">
        {modifiers.map((m) =>
          editId === m.id ? (
            <li
              key={m.id}
              className="flex flex-col gap-2 rounded-md border border-border/70 bg-[hsl(var(--field))] p-2 shadow-sm sm:flex-row sm:items-center"
            >
              <Input
                value={editForm.name_ru}
                onChange={(e) =>
                  setEditForm({ ...editForm, name_ru: e.target.value })
                }
                className="w-full sm:flex-1"
                placeholder="RU"
              />
              <Input
                value={editForm.name_en}
                onChange={(e) =>
                  setEditForm({ ...editForm, name_en: e.target.value })
                }
                className="w-full sm:flex-1"
                placeholder="EN"
              />
              <Input
                type="number"
                step="0.01"
                value={editForm.price}
                onChange={(e) =>
                  setEditForm({ ...editForm, price: e.target.value })
                }
                className="w-full sm:w-24"
              />
              <Button size="sm" onClick={() => handleSaveEdit(m)}>
                {t('common.save')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>
                {t('common.cancel')}
              </Button>
            </li>
          ) : (
            <li
              key={m.id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-border/65 bg-[hsl(var(--field))] px-3 py-2 shadow-sm transition-colors hover:bg-secondary/35"
            >
              <Switch
                checked={m.available}
                disabled={togglingId === m.id}
                onCheckedChange={(checked) => handleToggle(m, checked)}
              />
              <span className="min-w-0 flex-1 text-sm font-medium">
                {pickLang(m.name_ru, m.name_en, i18n.language)}
              </span>
              <span className="text-sm text-muted-foreground">
                {kopecksToRublesStr(m.price)} ₽
              </span>
              {isAdmin && (
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => startEdit(m)}
                    aria-label={t('pages.menu.modifiers.editAria', {
                      name: pickLang(m.name_ru, m.name_en, i18n.language),
                    })}
                    title={t('pages.menu.modifiers.editAria', {
                      name: pickLang(m.name_ru, m.name_en, i18n.language),
                    })}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => handleDelete(m)}
                    aria-label={t('pages.menu.modifiers.deleteAria', {
                      name: pickLang(m.name_ru, m.name_en, i18n.language),
                    })}
                    title={t('pages.menu.modifiers.deleteAria', {
                      name: pickLang(m.name_ru, m.name_en, i18n.language),
                    })}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
