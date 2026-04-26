import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ModifierResponse } from '@/api/menu';
import { setItemModifiers, ApiError } from '@/api/menu';
import { pickLang } from './utils';

// START_MODULE_CONTRACT
//   PURPOSE: Checkbox list that links/unlinks modifiers to a menu item via
//            setItemModifiers (PUT replaces the full set).
//   SCOPE:   Embedded in MenuItemFormDialog. Admin-only on the server.
//   DEPENDS: react, react-i18next, @/api/menu, ./utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4,
//            INV-002 (server enforces admin scope).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ModifiersPicker - admin-only modifier link manager for a menu item
// END_MODULE_MAP

interface Props {
  menuItemId: number;
  allModifiers: ModifierResponse[];
  selectedIds: number[];
  onChange: (nextIds: number[]) => void;
  disabled?: boolean;
  onError: (msg: string) => void;
}

// START_CONTRACT: ModifiersPicker
//   PURPOSE: Toggle a modifier into/out of the linked set for the given item;
//            persist via PUT setItemModifiers and reflect server response back.
//   INPUTS:  Props { menuItemId, allModifiers, selectedIds, onChange, disabled?, onError }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: PUT /api/v1/admin/menu/items/{id}/modifiers; 401 → onError.
//   LINKS:   INV-002.
// END_CONTRACT: ModifiersPicker
export function ModifiersPicker({
  menuItemId,
  allModifiers,
  selectedIds,
  onChange,
  disabled,
  onError,
}: Props) {
  const { t, i18n } = useTranslation();
  const [savingId, setSavingId] = useState<number | null>(null);

  async function handleToggle(mod: ModifierResponse, currentlyChecked: boolean) {
    if (disabled) return;
    const nextIds = currentlyChecked
      ? selectedIds.filter((x) => x !== mod.id)
      : [...selectedIds, mod.id];
    setSavingId(mod.id);
    try {
      const resp = await setItemModifiers(menuItemId, nextIds);
      onChange(resp.modifiers.map((x) => x.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('pages.menu.modifiersPicker.errorGeneric'));
      }
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{t('pages.menu.modifiersPicker.title')}</h3>
      {disabled && (
        <p className="text-xs text-muted-foreground">
          {t('pages.menu.modifiersPicker.saveFirstHint')}
        </p>
      )}
      {allModifiers.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t('pages.menu.modifiers.empty')}</p>
      ) : (
        <ul className="space-y-1">
          {allModifiers.map((m) => {
            const checked = selectedIds.includes(m.id);
            return (
              <li key={m.id}>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={checked}
                    disabled={disabled || savingId !== null}
                    onChange={() => handleToggle(m, checked)}
                  />
                  <span>{pickLang(m.name_ru, m.name_en, i18n.language)}</span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
