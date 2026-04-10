import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ModifierResponse } from '@/api/menu';
import { setItemModifiers, ApiError } from '@/api/menu';
import { pickLang } from './utils';

interface Props {
  menuItemId: number;
  allModifiers: ModifierResponse[];
  selectedIds: number[];
  onChange: (nextIds: number[]) => void;
  disabled?: boolean;
  onError: (msg: string) => void;
}

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
