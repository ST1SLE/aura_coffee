import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { SizeOptionResponse, SizeLabel } from '@/api/menu';
import {
  createSize,
  updateSize,
  deleteSize,
  ApiError,
} from '@/api/menu';
import { kopecksToRublesStr, rublesToKopecks } from './utils';

interface Props {
  menuItemId: number;
  sizes: SizeOptionResponse[];
  onChange: (sizes: SizeOptionResponse[]) => void;
  disabled?: boolean;
  onError: (msg: string) => void;
}

interface AddRow {
  label: SizeLabel;
  price: string;
}

const SIZE_LABELS: SizeLabel[] = ['S', 'M', 'L'];

const emptyRow = (): AddRow => ({ label: 'S', price: '' });

export function SizeOptionsEditor({ menuItemId, sizes, onChange, disabled, onError }: Props) {
  const { t } = useTranslation();
  const [addRow, setAddRow] = useState<AddRow>(emptyRow());
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editRow, setEditRow] = useState<AddRow>(emptyRow());

  async function handleAdd() {
    setAdding(true);
    try {
      const created = await createSize({
        menu_item_id: menuItemId,
        label: addRow.label,
        price: rublesToKopecks(addRow.price),
      });
      onChange([...sizes, created]);
      setAddRow(emptyRow());
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onError(t('pages.menu.sizes.duplicateLabel'));
      } else {
        onError(t('pages.menu.sizes.errorGeneric'));
      }
    } finally {
      setAdding(false);
    }
  }

  function startEdit(s: SizeOptionResponse) {
    setEditingId(s.id);
    setEditRow({
      label: s.label,
      price: kopecksToRublesStr(s.price),
    });
  }

  async function handleSaveEdit(s: SizeOptionResponse) {
    try {
      const updated = await updateSize(s.id, {
        label: editRow.label,
        price: rublesToKopecks(editRow.price),
      });
      onChange(sizes.map((x) => (x.id === s.id ? updated : x)));
      setEditingId(null);
    } catch {
      onError(t('pages.menu.sizes.errorGeneric'));
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t('pages.menu.sizes.deleteSizeConfirm'))) return;
    try {
      await deleteSize(id);
      onChange(sizes.filter((s) => s.id !== id));
    } catch {
      onError(t('pages.menu.sizes.errorGeneric'));
    }
  }

  if (disabled) {
    return (
      <div className="rounded-md border p-4 text-sm text-muted-foreground">
        {t('pages.menu.sizes.disabledHint')}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium">{t('pages.menu.sizes.title')}</p>

      {sizes.length === 0 && (
        <p className="text-sm text-muted-foreground">{t('pages.menu.sizes.empty')}</p>
      )}

      <div className="space-y-2">
        {sizes.map((s) =>
          editingId === s.id ? (
            <div key={s.id} className="flex gap-2 items-center">
              <select
                value={editRow.label}
                onChange={(e) => setEditRow({ ...editRow, label: e.target.value as SizeLabel })}
                className="flex h-9 w-20 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {SIZE_LABELS.map((lbl) => (
                  <option key={lbl} value={lbl}>{lbl}</option>
                ))}
              </select>
              <Input
                type="number"
                step="0.01"
                value={editRow.price}
                onChange={(e) => setEditRow({ ...editRow, price: e.target.value })}
                placeholder={t('pages.menu.sizes.price')}
                className="w-20"
              />
              <Button size="sm" onClick={() => handleSaveEdit(s)}>
                {t('common.save')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                {t('common.cancel')}
              </Button>
            </div>
          ) : (
            <div key={s.id} className="flex gap-2 items-center text-sm">
              <span className="w-24 font-medium">{s.label}</span>
              <span className="w-20">{kopecksToRublesStr(s.price)} ₽</span>
              <Button size="sm" variant="ghost" onClick={() => startEdit(s)}>
                {t('common.edit')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-destructive"
                onClick={() => handleDelete(s.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ),
        )}
      </div>

      {/* строка добавления */}
      <div className="flex gap-2 items-center">
        <select
          value={addRow.label}
          onChange={(e) => setAddRow({ ...addRow, label: e.target.value as SizeLabel })}
          className="flex h-9 w-20 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {SIZE_LABELS.map((lbl) => (
            <option key={lbl} value={lbl}>{lbl}</option>
          ))}
        </select>
        <Input
          type="number"
          step="0.01"
          value={addRow.price}
          onChange={(e) => setAddRow({ ...addRow, price: e.target.value })}
          placeholder="0.00"
          className="w-20"
        />
        <Button size="sm" variant="outline" onClick={handleAdd} disabled={adding}>
          <Plus className="h-4 w-4 mr-1" />
          {adding ? t('pages.menu.sizes.adding') : t('pages.menu.sizes.add')}
        </Button>
      </div>
    </div>
  );
}
