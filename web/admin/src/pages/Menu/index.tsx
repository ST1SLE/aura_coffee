import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CategoryList } from './CategoryList';
import { MenuItemsTable } from './MenuItemsTable';
import { ModifiersPanel } from './ModifiersPanel';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import type { CategoryResponse, ModifierResponse } from '@/api/menu';
import { listModifiers, ApiError } from '@/api/menu';

// TODO: wire via staff-auth — заменить на реальное получение роли из auth-стора
function useCurrentRole(): 'admin' | 'barista' {
  return 'admin';
}

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
