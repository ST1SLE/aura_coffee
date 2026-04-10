import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { ModifierResponse } from '@/api/menu';
import {
  listModifiers,
  createModifier,
  updateModifier,
  deleteModifier,
  setModifierAvailability,
  ApiError,
} from '@/api/menu';
import { kopecksToRublesStr, rublesToKopecks } from './utils';

interface Props {
  currentRole: 'admin' | 'barista';
  onError: (msg: string) => void;
}

interface FormRow {
  name: string;
  price: string;
}

const emptyForm = (): FormRow => ({ name: '', price: '' });

export function ModifiersPanel({ currentRole, onError }: Props) {
  const { t } = useTranslation();
  const [modifiers, setModifiers] = useState<ModifierResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [addForm, setAddForm] = useState<FormRow>(emptyForm());
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormRow>(emptyForm());
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const isAdmin = currentRole === 'admin';

  useEffect(() => {
    setLoading(true);
    listModifiers()
      .then(setModifiers)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
        else onError(t('common.error'));
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAdd() {
    if (!addForm.name.trim()) return;
    setAdding(true);
    try {
      const created = await createModifier({
        name: addForm.name.trim(),
        price_kopecks: rublesToKopecks(addForm.price),
      });
      setModifiers((prev) => [...prev, created]);
      setAddForm(emptyForm());
      setShowAdd(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('pages.menu.modifiers.errorGeneric'));
    } finally {
      setAdding(false);
    }
  }

  function startEdit(m: ModifierResponse) {
    setEditId(m.id);
    setEditForm({ name: m.name, price: kopecksToRublesStr(m.price_kopecks) });
  }

  async function handleSaveEdit(m: ModifierResponse) {
    try {
      const updated = await updateModifier(m.id, {
        name: editForm.name.trim() || m.name,
        price_kopecks: rublesToKopecks(editForm.price),
      });
      setModifiers((prev) => prev.map((x) => (x.id === m.id ? updated : x)));
      setEditId(null);
    } catch {
      onError(t('pages.menu.modifiers.errorGeneric'));
    }
  }

  async function handleDelete(m: ModifierResponse) {
    if (!confirm(t('pages.menu.modifiers.deleteConfirm'))) return;
    try {
      await deleteModifier(m.id);
      setModifiers((prev) => prev.filter((x) => x.id !== m.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    }
  }

  async function handleToggle(m: ModifierResponse, next: boolean) {
    setTogglingId(m.id);
    try {
      const updated = await setModifierAvailability(m.id, next);
      setModifiers((prev) => prev.map((x) => (x.id === m.id ? updated : x)));
    } catch {
      onError(t('pages.menu.modifiers.errorToggle'));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t('pages.menu.modifiers.title')}</h2>
        {isAdmin && (
          <Button size="sm" variant="outline" onClick={() => setShowAdd((v) => !v)}>
            <Plus className="h-4 w-4 mr-1" />
            {t('pages.menu.modifiers.newModifier')}
          </Button>
        )}
      </div>

      {/* Форма добавления */}
      {isAdmin && showAdd && (
        <div className="flex gap-2 items-end border rounded-md p-3">
          <div className="space-y-1 flex-1">
            <Label>{t('pages.menu.modifiers.name')}</Label>
            <Input
              value={addForm.name}
              onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
              placeholder={t('pages.menu.modifiers.namePlaceholder')}
            />
          </div>
          <div className="space-y-1 w-28">
            <Label>{t('pages.menu.modifiers.price')}</Label>
            <Input
              type="number"
              step="0.01"
              value={addForm.price}
              onChange={(e) => setAddForm({ ...addForm, price: e.target.value })}
              placeholder="0.00"
            />
          </div>
          <Button disabled={adding} onClick={handleAdd}>
            {adding ? t('pages.menu.modifiers.saving') : t('pages.menu.modifiers.save')}
          </Button>
          <Button variant="ghost" onClick={() => setShowAdd(false)}>
            {t('pages.menu.modifiers.cancel')}
          </Button>
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">{t('common.loading')}</p>}
      {!loading && modifiers.length === 0 && (
        <p className="text-sm text-muted-foreground">{t('pages.menu.modifiers.empty')}</p>
      )}

      <ul className="space-y-2">
        {modifiers.map((m) =>
          editId === m.id ? (
            <li key={m.id} className="flex gap-2 items-center border rounded-md p-2">
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                className="flex-1"
              />
              <Input
                type="number"
                step="0.01"
                value={editForm.price}
                onChange={(e) => setEditForm({ ...editForm, price: e.target.value })}
                className="w-24"
              />
              <Button size="sm" onClick={() => handleSaveEdit(m)}>
                {t('common.save')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>
                {t('common.cancel')}
              </Button>
            </li>
          ) : (
            <li key={m.id} className="flex items-center gap-3 rounded-md border px-3 py-2">
              <Switch
                checked={m.available}
                disabled={togglingId === m.id}
                onCheckedChange={(checked) => handleToggle(m, checked)}
              />
              <span className="flex-1 text-sm font-medium">{m.name}</span>
              <span className="text-sm text-muted-foreground">
                {kopecksToRublesStr(m.price_kopecks)} ₽
              </span>
              {isAdmin && (
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => startEdit(m)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => handleDelete(m)}
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
