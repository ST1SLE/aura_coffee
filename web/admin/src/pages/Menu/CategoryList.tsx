import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { CategoryResponse, CategoryType } from '@/api/menu';
import { listCategories, createCategory, updateCategory, deleteCategory, ApiError } from '@/api/menu';
import { pickLang } from './utils';

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
  const { t, i18n } = useTranslation();
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [newNameRu, setNewNameRu] = useState('');
  const [newNameEn, setNewNameEn] = useState('');
  const [newType, setNewType] = useState<CategoryType>('drink');
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editNameRu, setEditNameRu] = useState('');
  const [editNameEn, setEditNameEn] = useState('');
  const [editType, setEditType] = useState<CategoryType>('drink');
  const [editSortOrder, setEditSortOrder] = useState<string>('0');
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
    if (!newNameRu.trim() || !newNameEn.trim()) return;
    setAdding(true);
    try {
      const created = await createCategory({
        type: newType,
        name_ru: newNameRu.trim(),
        name_en: newNameEn.trim(),
        sort_order: categories.length,
        is_visible: true,
      });
      const updated = [...categories, created];
      setCategories(updated);
      onCategoriesLoaded(updated);
      setNewNameRu('');
      setNewNameEn('');
      setNewType('drink');
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { detail?: Array<{ loc: string[] }> } | null;
        const fields = body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
        onError(t('pages.menu.itemForm.error422', { fields }));
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('common.error'));
      }
    } finally {
      setAdding(false);
    }
  }

  function startEdit(cat: CategoryResponse) {
    setEditId(cat.id);
    setEditNameRu(cat.name_ru);
    setEditNameEn(cat.name_en);
    setEditType(cat.type);
    setEditSortOrder(String(cat.sort_order));
  }

  async function handleSaveEdit(cat: CategoryResponse) {
    if (!editNameRu.trim() || !editNameEn.trim()) return;
    const parsed = parseInt(editSortOrder, 10);
    const sort_order = Number.isNaN(parsed) ? cat.sort_order : parsed;
    try {
      const updated = await updateCategory(cat.id, {
        name_ru: editNameRu.trim(),
        name_en: editNameEn.trim(),
        type: editType,
        sort_order,
      });
      const next = categories
        .map((c) => (c.id === cat.id ? updated : c))
        .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
      setCategories(next);
      onCategoriesLoaded(next);
      setEditId(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { detail?: Array<{ loc: string[] }> } | null;
        const fields = body?.detail?.map((d) => d.loc.slice(-1)[0]).join(', ') ?? '';
        onError(t('pages.menu.itemForm.error422', { fields }));
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('common.error'));
      }
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

  const typeOptions: CategoryType[] = ['drink', 'food', 'merch', 'modifier'];

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
            <li key={cat.id} className="space-y-1 p-1 border rounded-md">
              <div className="flex gap-1">
                <Input
                  value={editNameRu}
                  onChange={(e) => setEditNameRu(e.target.value)}
                  className="h-7 text-sm"
                  placeholder="RU"
                  autoFocus
                />
                <Input
                  value={editNameEn}
                  onChange={(e) => setEditNameEn(e.target.value)}
                  className="h-7 text-sm"
                  placeholder="EN"
                />
              </div>
              <div className="flex gap-1">
                <select
                  value={editType}
                  onChange={(e) => setEditType(e.target.value as CategoryType)}
                  className="flex h-7 flex-1 rounded-md border border-input bg-transparent px-2 py-0.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {typeOptions.map((tp) => (
                    <option key={tp} value={tp}>
                      {t(`pages.menu.categories.typeOptions.${tp}`)}
                    </option>
                  ))}
                </select>
                <Input
                  type="number"
                  min="0"
                  value={editSortOrder}
                  onChange={(e) => setEditSortOrder(e.target.value)}
                  className="h-7 w-14 text-sm"
                  placeholder="#"
                  title={t('pages.menu.categories.sortOrder')}
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
              </div>
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
              <span className="flex-1 text-sm truncate">
                {pickLang(cat.name_ru, cat.name_en, i18n.language)}
              </span>
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
        <div className="space-y-2 border rounded-md p-2">
          <div className="space-y-1">
            <Label htmlFor="cat-name-ru" className="text-xs">
              {t('pages.menu.categories.nameRu')}
            </Label>
            <Input
              id="cat-name-ru"
              value={newNameRu}
              onChange={(e) => setNewNameRu(e.target.value)}
              className="h-7 text-sm"
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cat-name-en" className="text-xs">
              {t('pages.menu.categories.nameEn')}
            </Label>
            <Input
              id="cat-name-en"
              value={newNameEn}
              onChange={(e) => setNewNameEn(e.target.value)}
              className="h-7 text-sm"
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cat-type" className="text-xs">
              {t('pages.menu.categories.type')}
            </Label>
            <select
              id="cat-type"
              value={newType}
              onChange={(e) => setNewType(e.target.value as CategoryType)}
              className="flex h-7 w-full rounded-md border border-input bg-transparent px-2 py-0.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {typeOptions.map((tp) => (
                <option key={tp} value={tp}>
                  {t(`pages.menu.categories.typeOptions.${tp}`)}
                </option>
              ))}
            </select>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 w-full"
            disabled={adding}
            onClick={handleAdd}
          >
            <Plus className="h-3 w-3 mr-1" />
            {t('pages.menu.categories.newCategory')}
          </Button>
        </div>
      )}
    </div>
  );
}
