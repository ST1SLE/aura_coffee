import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CategoryList } from './CategoryList';
import { MenuItemsTable } from './MenuItemsTable';
import { ModifiersPanel } from './ModifiersPanel';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import type { CategoryResponse, ModifierResponse } from '@/api/menu';
import { listModifiers, ApiError } from '@/api/menu';
import { useCurrentRole } from '@/lib/auth';

// START_MODULE_CONTRACT
//   PURPOSE: Composite Menu management page — three columns: category list,
//            items for the selected category, modifiers panel. Currently the
//            module barrel (this file is also imported as '@/pages/Menu').
//   SCOPE:   Mounted at /menu under the admin/barista layout. Barista sees
//            the same page but child components hide CRUD buttons via the
//            currentRole prop (server still enforces — INV-002/INV-010).
//   DEPENDS: react, react-i18next, @/api/menu, @/lib/auth, sibling Menu*.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4 menu CRUD,
//            INV-002 (server enforces; client filters CRUD UI for barista),
//            INV-010 (role isolation — courier never reaches this page).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuPage - top-level menu management surface for admin and barista
// END_MODULE_MAP

// START_CONTRACT: MenuPage
//   PURPOSE: Compose the menu management UI — fetch modifiers once on mount,
//            track selected category and the master list of categories/modifiers,
//            and pass currentRole down so child components can hide admin-only
//            controls. Returns null for null/courier roles to satisfy types
//            (those roles are unreachable here per ProtectedRoute).
//   INPUTS:  none.
//   OUTPUTS: JSX.Element | null.
//   SIDE_EFFECTS: GET /api/v1/admin/menu/modifiers on mount; notifier toasts on error.
//   LINKS:   INV-002 (admin and barista can read menu; only admin may CRUD —
//            child components gate buttons by currentRole, but the API is the
//            real boundary), INV-010.
// END_CONTRACT: MenuPage
export function MenuPage() {
  const { t } = useTranslation();
  const currentRole = useCurrentRole();
  const { notifications, notify, dismiss } = useNotifier();

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [modifiers, setModifiers] = useState<ModifierResponse[]>([]);

  function handleError(msg: string) {
    notify(msg, 'error');
  }

  useEffect(() => {
    listModifiers()
      .then(setModifiers)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) handleError(t('common.sessionExpired'));
        else handleError(t('common.error'));
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Страница обёрнута в ProtectedRoute с allowedRoles=['admin','barista'],
  // поэтому null/courier тут недостижимы — early return ради сужения типа.
  if (currentRole === null || currentRole === 'courier') return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('pages.menu.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('pages.menu.description')}</p>
      </div>

      <div className="flex gap-6 items-start">
        {/* Левая колонка — категории */}
        <CategoryList
          selectedId={selectedCategoryId}
          onSelect={setSelectedCategoryId}
          onCategoriesLoaded={setCategories}
          currentRole={currentRole}
          onError={handleError}
        />

        {/* Центральная колонка — позиции меню */}
        <div className="flex-1 min-w-0">
          <MenuItemsTable
            categoryId={selectedCategoryId}
            categories={categories}
            modifiers={modifiers}
            currentRole={currentRole}
            onError={handleError}
          />
        </div>
      </div>

      {/* Нижняя секция — модификаторы */}
      <div className="border-t pt-6">
        <ModifiersPanel
          modifiers={modifiers}
          onModifiersChange={setModifiers}
          currentRole={currentRole}
          onError={handleError}
        />
      </div>

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
