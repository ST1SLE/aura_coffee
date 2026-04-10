import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { listCategories, listMenuItems } from '@/api/menu';
import type { CategoryResponse, MenuItemResponse } from '@/api/menuTypes';
import { Button } from '@/components/ui/button';
import { MenuItemCard } from './MenuItemCard';
import { ItemDetail } from './ItemDetail';

export function MenuPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';

  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [items, setItems] = useState<MenuItemResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<MenuItemResponse | null>(null);

  async function load() {
    setLoading(true);
    setError(false);
    try {
      const [cats, its] = await Promise.all([listCategories(), listMenuItems()]);
      setCategories([...cats].sort((a, b) => a.sort_order - b.sort_order));
      setItems(its);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div className="p-4 space-y-4">
        <div className="h-6 w-32 animate-pulse rounded bg-muted" />
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 flex flex-col items-center gap-4">
        <p className="text-destructive">{t('menu.error')}</p>
        <Button variant="outline" onClick={load}>{t('menu.retry')}</Button>
      </div>
    );
  }

  if (categories.length === 0) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        {t('menu.empty')}
      </div>
    );
  }

  return (
    <>
      <div className="p-4 space-y-8">
        {categories.map((cat) => {
          const catItems = items.filter((it) => it.category_id === cat.id);
          if (catItems.length === 0) return null;
          return (
            <section key={cat.id}>
              <h2 className="text-lg font-semibold mb-3">
                {lang === 'ru' ? cat.name_ru : cat.name_en}
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {catItems
                  .slice()
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((item) => (
                    <MenuItemCard
                      key={item.id}
                      item={item}
                      lang={lang}
                      onOpen={() => setSelected(item)}
                    />
                  ))}
              </div>
            </section>
          );
        })}
      </div>

      {selected && (
        <ItemDetail
          item={selected}
          lang={lang}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
