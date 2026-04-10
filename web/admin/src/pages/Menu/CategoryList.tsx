import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { CategoryResponse } from '@/api/menu';
import { listCategories, createCategory, updateCategory, deleteCategory, ApiError } from '@/api/menu';

interface Props {
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onCategoriesLoaded: (cats: CategoryResponse[]) => void;
  currentRole: 'admin' | 'barista';
  onError: (msg: string) => void;
}

export function CategoryList({
  selectedId,
  onSelect,
  onCategoriesLoaded,
  currentRole,
  onError,
}: Props) {
  const { t } = useTranslation();
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const isAdmin = currentRole === 'admin';

  useEffect(() => {
    listCategories()
      .then((cats) => {
        setCategories(cats);
        onCategoriesLoaded(cats);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
        else onError(t('common.error'));
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAdd() {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      const created = await createCategory({ name: newName.trim() });
      const updated = [...categories, created];
      setCategories(updated);
      onCategoriesLoaded(updated);
      setNewName('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    } finally {
      setAdding(false);
    }
  }

  function startEdit(cat: CategoryResponse) {
    setEditId(cat.id);
    setEditName(cat.name);
  }

  async function handleSaveEdit(cat: CategoryResponse) {
    if (!editName.trim()) return;
    try {
      const updated = await updateCategory(cat.id, { name: editName.trim() });
      const next = categories.map((c) => (c.id === cat.id ? updated : c));
      setCategories(next);
      onCategoriesLoaded(next);
      setEditId(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onError(t('common.sessionExpired'));
      else onError(t('common.error'));
    }
  }

  async function handleDelete(cat: CategoryResponse) {
    if (!confirm(t('pages.menu.categories.deleteConfirm'))) return;
    try {
      await deleteCategory(cat.id);
      const next = categories.filter((c) => c.id !== cat.id);
      setCategories(next);
      onCategoriesLoaded(next);
      if (selectedId === cat.id) onSelect(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onError(t('pages.menu.categories.deleteHasItems'));
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('common.error'));
      }
    }
  }

  return (
    <div className="w-56 shrink-0 space-y-2">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
        {t('pages.menu.categories.title')}
      </h2>

      {/* Кнопка "Все" */}
      <button
        className={`w-full text-left text-sm px-2 py-1.5 rounded-md transition-colors ${
          selectedId === null ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'
        }`}
        onClick={() => onSelect(null)}
      >
        {t('pages.menu.categories.allCategories')}
      </button>

      {categories.length === 0 && (
        <p className="text-xs text-muted-foreground">{t('pages.menu.categories.empty')}</p>
      )}

      <ul className="space-y-1">
        {categories.map((cat) =>
          editId === cat.id ? (
            <li key={cat.id} className="flex gap-1">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="h-7 text-sm"
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit(cat)}
              />
              <Button size="sm" className="h-7 px-2" onClick={() => handleSaveEdit(cat)}>
                ✓
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2"
                onClick={() => setEditId(null)}
              >
                ✕
              </Button>
            </li>
          ) : (
            <li
              key={cat.id}
              className={`group flex items-center gap-1 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                selectedId === cat.id
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent'
              }`}
              onClick={() => onSelect(cat.id)}
            >
              <span className="flex-1 text-sm truncate">{cat.name}</span>
              {isAdmin && (
                <span
                  className="hidden group-hover:flex gap-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    className="p-0.5 hover:opacity-70"
                    onClick={() => startEdit(cat)}
                    title={t('pages.menu.categories.editCategory')}
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                  <button
                    className="p-0.5 hover:opacity-70 text-destructive"
                    onClick={() => handleDelete(cat)}
                    title={t('pages.menu.categories.deleteCategory')}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              )}
            </li>
          ),
        )}
      </ul>

      {isAdmin && (
        <div className="flex gap-1">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t('pages.menu.categories.namePlaceholder')}
            className="h-7 text-sm"
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          />
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2"
            disabled={adding}
            onClick={handleAdd}
          >
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      )}
    </div>
  );
}
