import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchPublicMenu } from '@/api/menu';
import type { PublicMenuResponse, PublicMenuItem } from '@/api/menuTypes';
import { Button } from '@/components/ui/button';
import { MenuItemCard } from './MenuItemCard';
import { ItemDetail } from './ItemDetail';

// START_MODULE_CONTRACT
//   PURPOSE: /menu route — load the menu localized to current i18next language,
//            re-load on language change, render horizontal category browsing
//            plus media-led cards, and open ItemDetail when a card is tapped.
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
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);

  async function load(language: 'ru' | 'en') {
    setLoading(true);
    setError(false);
    try {
      const data = await fetchPublicMenu(language);
      setMenu(data);
      setActiveCategoryId((current) => {
        const categoriesWithItems = data.categories.filter(
          (category) => category.items.length > 0,
        );
        if (
          current != null &&
          categoriesWithItems.some((category) => category.id === current)
        ) {
          return current;
        }
        return categoriesWithItems[0]?.id ?? null;
      });
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
    return () => {
      i18n.off('languageChanged', handleLangChange);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleCategories =
    menu?.categories.filter((category) => category.items.length > 0) ?? [];

  function handleCategoryClick(categoryId: number) {
    setActiveCategoryId(categoryId);
    document
      .getElementById(`menu-category-${categoryId}`)
      ?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }

  if (loading) {
    return (
      <div className="space-y-5 px-4 py-5 md:px-6">
        <div className="h-32 animate-pulse rounded-lg bg-muted" />
        <div className="flex gap-2 overflow-hidden rounded-lg bg-card/60 py-1">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-10 w-28 shrink-0 animate-pulse rounded-full bg-muted"
            />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-destructive">{t('menu.error')}</p>
        <Button variant="outline" onClick={() => load(lang)}>
          {t('menu.retry')}
        </Button>
      </div>
    );
  }

  if (!menu || visibleCategories.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4 text-center text-muted-foreground">
        {t('menu.empty')}
      </div>
    );
  }

  return (
    <>
      <div className="space-y-7 px-4 py-5 md:px-6">
        <div className="overflow-hidden rounded-lg border border-border/70 bg-brand-sage text-brand-sage-foreground shadow-[0_18px_45px_rgba(58,46,37,0.10)]">
          <div className="grid min-h-36 gap-4 p-4 md:grid-cols-[minmax(0,1fr)_14rem] md:p-5">
            <div className="flex flex-col justify-end gap-2">
              <h1 className="max-w-2xl text-4xl font-semibold leading-none tracking-normal md:text-5xl">
                {t('menu.title')}
              </h1>
              <p className="max-w-xl text-sm leading-6 text-foreground/75">
                {t('pages.home.description')}
              </p>
            </div>
            <div className="hidden rounded-lg border border-border/60 bg-card/70 p-3 shadow-[0_12px_26px_rgba(58,46,37,0.08)] md:block">
              <div className="flex h-full flex-col justify-between">
                <span className="font-display text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t('menu.categories')}
                </span>
                <div className="mt-4 flex flex-wrap gap-2">
                  {visibleCategories.slice(0, 4).map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => handleCategoryClick(cat.id)}
                      className="font-display min-h-9 rounded-full border border-border/70 bg-background/80 px-3 text-xs font-semibold text-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
                    >
                      {cat.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <nav
          aria-label={t('menu.categories')}
          className="sticky top-[4.6rem] z-20 -mx-4 flex gap-2 overflow-x-auto border-y border-border/70 bg-background/90 px-4 py-3 shadow-[0_10px_28px_rgba(58,46,37,0.06)] backdrop-blur-xl md:top-[4.9rem] md:mx-0 md:rounded-lg md:border md:px-3"
        >
          {visibleCategories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => handleCategoryClick(cat.id)}
              className={[
                'font-display min-h-10 shrink-0 rounded-full border px-4 text-sm font-semibold transition-colors',
                activeCategoryId === cat.id
                  ? 'border-primary bg-primary text-primary-foreground shadow-[0_10px_22px_rgba(108,122,85,0.16)]'
                  : 'border-border/70 bg-card text-muted-foreground hover:bg-secondary hover:text-secondary-foreground',
              ].join(' ')}
            >
              {cat.name}
            </button>
          ))}
        </nav>

        <div className="space-y-8">
          {visibleCategories.map((cat) => {
            return (
              <section
                key={cat.id}
                id={`menu-category-${cat.id}`}
                aria-labelledby={`menu-category-heading-${cat.id}`}
                className="scroll-mt-28 space-y-3"
              >
                <h2
                  id={`menu-category-heading-${cat.id}`}
                  className="text-2xl font-semibold tracking-normal"
                >
                  {cat.name}
                </h2>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
