import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchPublicMenu } from '@/api/menu';
import type { PublicMenuResponse, PublicMenuItem } from '@/api/menuTypes';
import { Button } from '@/components/ui/button';
import { MenuItemCard } from './MenuItemCard';
import { ItemDetail } from './ItemDetail';

// START_MODULE_CONTRACT
//   PURPOSE: /menu route — load the menu localized to current i18next language,
//            re-load on language change, render category sections of cards,
//            and open ItemDetail when a card is tapped.
//   SCOPE:   MenuPage component.
//   DEPENDS: react, react-i18next, @/api/menu (fetchPublicMenu), @/api/menuTypes,
//            @/components/ui/button, ./MenuItemCard, ./ItemDetail.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuPage  - /menu route — categories + grid of cards + item modal
// END_MODULE_MAP

// START_CONTRACT: MenuPage
//   PURPOSE: Fetch and render the bilingual menu, opening ItemDetail when a
//            card is selected.
//   INPUTS:  none.
//   OUTPUTS: JSX — skeleton / error / empty / category grid (+ modal).
//   SIDE_EFFECTS: HTTP GET /api/v1/menu via fetchPublicMenu on mount; reloads
//                 on i18next 'languageChanged' event (subscribe + cleanup).
//   LINKS:   PDD §3.
// END_CONTRACT: MenuPage
export function MenuPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';

  const [menu, setMenu] = useState<PublicMenuResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<PublicMenuItem | null>(null);

  async function load(language: 'ru' | 'en') {
    setLoading(true);
    setError(false);
    try {
      const data = await fetchPublicMenu(language);
      setMenu(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(lang);

    // Перезагружаем меню при смене языка через react-i18next
    function handleLangChange(newLang: string) {
      const l = newLang.startsWith('ru') ? 'ru' : 'en';
      load(l);
    }

    i18n.on('languageChanged', handleLangChange);
    return () => { i18n.off('languageChanged', handleLangChange); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <Button variant="outline" onClick={() => load(lang)}>{t('menu.retry')}</Button>
      </div>
    );
  }

  if (!menu || menu.categories.length === 0) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        {t('menu.empty')}
      </div>
    );
  }

  return (
    <>
      <div className="p-4 space-y-8">
        {menu.categories.map((cat) => {
          if (cat.items.length === 0) return null;
          return (
            <section key={cat.id}>
              <h2 className="text-lg font-semibold mb-3">{cat.name}</h2>
              <div className="grid grid-cols-2 gap-3">
                {cat.items.map((item) => (
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
