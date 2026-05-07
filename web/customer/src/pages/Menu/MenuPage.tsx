import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { fetchPublicMenu } from '@/api/menu';
import type { PublicMenuResponse, PublicMenuItem } from '@/api/menuTypes';
import { Button } from '@/components/ui/button';
import { MenuItemCard } from './MenuItemCard';
import { ItemDetail } from './ItemDetail';

// START_MODULE_CONTRACT
//   PURPOSE: /menu route — load the menu localized to current i18next language,
//            re-load on language change, honor /menu/:categoryId deep links,
//            render scroll-synced category browsing plus media-led cards, and
//            open ItemDetail when a card is tapped.
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

const ACTIVE_CATEGORY_ANCHOR_PX = 170;
const SCROLL_BOTTOM_TOLERANCE_PX = 8;

// START_CONTRACT: MenuPage
//   PURPOSE: Fetch and render the bilingual menu, opening ItemDetail when a
//            card is selected; sync /menu/:categoryId to the category rail.
//   INPUTS:  none.
//   OUTPUTS: JSX — skeleton / error / empty / category rail + grid (+ modal).
//   SIDE_EFFECTS: HTTP GET /api/v1/menu via fetchPublicMenu on mount; reloads
//                 on i18next 'languageChanged' event (subscribe + cleanup);
//                 reads menu section positions on scroll/resize to keep the
//                 active category chip in sync with the viewport;
//                 scrolls to a valid route category id after menu load.
//   LINKS:   PDD §3.
// END_CONTRACT: MenuPage
export function MenuPage() {
  const { t, i18n } = useTranslation();
  const { categoryId } = useParams();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const routeCategoryId = categoryId ? Number(categoryId) : Number.NaN;
  const validRouteCategoryId = Number.isInteger(routeCategoryId)
    ? routeCategoryId
    : null;
  const hasRouteCategory = categoryId != null;

  const [menu, setMenu] = useState<PublicMenuResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<PublicMenuItem | null>(null);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const lastTriggerRef = useRef<HTMLElement | null>(null);
  const shouldRestoreFocusRef = useRef(false);
  const categoryButtonRefs = useRef(new Map<number, HTMLButtonElement>());

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
  const visibleCategoryKey = visibleCategories
    .map((category) => category.id)
    .join('|');

  useEffect(() => {
    if (!hasRouteCategory || visibleCategories.length === 0) return;

    const matchedCategoryId =
      validRouteCategoryId != null &&
      visibleCategories.some((category) => category.id === validRouteCategoryId)
        ? validRouteCategoryId
        : null;
    const nextCategoryId = matchedCategoryId ?? visibleCategories[0]?.id ?? null;
    if (nextCategoryId == null) return;

    setActiveCategoryId(nextCategoryId);
    if (matchedCategoryId != null) {
      document
        .getElementById(`menu-category-${matchedCategoryId}`)
        ?.scrollIntoView?.({ block: 'start' });
    }
  }, [hasRouteCategory, validRouteCategoryId, visibleCategoryKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (visibleCategories.length === 0) return;

    function updateActiveCategoryFromScroll() {
      let nextCategoryId = visibleCategories[0]?.id ?? null;
      let nearestPassedTop = Number.NEGATIVE_INFINITY;

      for (const category of visibleCategories) {
        const node = document.getElementById(`menu-category-${category.id}`);
        if (!node) continue;

        const rect = node.getBoundingClientRect();
        if (
          rect.top <= ACTIVE_CATEGORY_ANCHOR_PX &&
          rect.bottom > ACTIVE_CATEGORY_ANCHOR_PX
        ) {
          nextCategoryId = category.id;
          break;
        }

        if (
          rect.top <= ACTIVE_CATEGORY_ANCHOR_PX &&
          rect.top > nearestPassedTop
        ) {
          nearestPassedTop = rect.top;
          nextCategoryId = category.id;
        }
      }

      const scrollBottom = window.scrollY + window.innerHeight;
      const pageBottom = document.documentElement.scrollHeight;
      if (pageBottom - scrollBottom <= SCROLL_BOTTOM_TOLERANCE_PX) {
        nextCategoryId =
          visibleCategories[visibleCategories.length - 1]?.id ?? nextCategoryId;
      }

      setActiveCategoryId((current) =>
        current === nextCategoryId ? current : nextCategoryId,
      );
    }

    if (!hasRouteCategory) {
      updateActiveCategoryFromScroll();
    }
    window.addEventListener('scroll', updateActiveCategoryFromScroll, {
      passive: true,
    });
    window.addEventListener('resize', updateActiveCategoryFromScroll);

    return () => {
      window.removeEventListener('scroll', updateActiveCategoryFromScroll);
      window.removeEventListener('resize', updateActiveCategoryFromScroll);
    };
  }, [hasRouteCategory, visibleCategoryKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeCategoryId == null) return;
    categoryButtonRefs.current.get(activeCategoryId)?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    });
  }, [activeCategoryId]);

  function handleCategoryClick(categoryId: number) {
    setActiveCategoryId(categoryId);
    document
      .getElementById(`menu-category-${categoryId}`)
      ?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }

  function handleOpenItem(item: PublicMenuItem, trigger: HTMLElement) {
    lastTriggerRef.current = trigger;
    shouldRestoreFocusRef.current = false;
    setSelected(item);
  }

  function handleCloseItem() {
    shouldRestoreFocusRef.current = true;
    setSelected(null);
  }

  useEffect(() => {
    if (selected !== null || !shouldRestoreFocusRef.current) return;
    shouldRestoreFocusRef.current = false;
    lastTriggerRef.current?.focus();
  }, [selected]);

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
        <div className="aura-surface overflow-hidden rounded-lg">
          <div className="flex min-h-36 flex-col justify-end gap-2 p-4 md:p-5">
            <h1 className="max-w-2xl text-4xl font-semibold leading-none tracking-normal md:text-5xl">
              {t('menu.title')}
            </h1>
            <p className="max-w-xl text-sm leading-6 text-muted-foreground">
              {t('pages.home.description')}
            </p>
          </div>
        </div>

        <nav
          aria-label={t('menu.categories')}
          className="aura-scrollbar-none sticky top-[4.6rem] z-20 -mx-4 flex gap-2 overflow-x-auto border-y border-border/70 bg-background/90 px-4 py-3 shadow-[0_10px_28px_rgba(58,46,37,0.06)] backdrop-blur-xl md:top-[4.9rem] md:mx-0 md:rounded-lg md:border md:px-3"
        >
          {visibleCategories.map((cat) => (
            <button
              key={cat.id}
              ref={(node) => {
                if (node) {
                  categoryButtonRefs.current.set(cat.id, node);
                } else {
                  categoryButtonRefs.current.delete(cat.id);
                }
              }}
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
                data-category-id={cat.id}
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
                      onOpen={(trigger) => handleOpenItem(item, trigger)}
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
          onClose={handleCloseItem}
        />
      )}
    </>
  );
}
