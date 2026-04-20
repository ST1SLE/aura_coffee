import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  suggest,
  MapsUnavailableError,
  type SuggestResult,
  type MapsLang,
} from '@/api/yandex_maps';

export interface AddressValue {
  text: string;
  lat: number | null;
  lon: number | null;
}

interface Props {
  value: AddressValue;
  onChange: (next: AddressValue) => void;
  lang: MapsLang;
  inputId?: string;
  required?: boolean;
}

const MIN_QUERY_LEN = 3;
const DEBOUNCE_MS = 300;

// AddressAutocomplete: debounced-input с dropdown-подсказками Яндекс.Карт.
// На 503/network — уходит в degraded-режим на всю сессию монтирования (§8.3).
export function AddressAutocomplete({
  value,
  onChange,
  lang,
  inputId,
  required,
}: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState(value.text);
  const [items, setItems] = useState<SuggestResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [degraded, setDegraded] = useState(false);

  // Монотонный счётчик: гарантия, что stale-ответ не перетрёт свежий.
  const reqIdRef = useRef(0);

  useEffect(() => {
    if (degraded) return;
    if (query.length < MIN_QUERY_LEN) {
      setItems([]);
      setOpen(false);
      return;
    }

    const id = ++reqIdRef.current;
    setLoading(true);
    const timer = setTimeout(() => {
      suggest(query, lang)
        .then((result) => {
          if (id !== reqIdRef.current) return;
          setItems(result);
          setOpen(true);
          setLoading(false);
        })
        .catch((err) => {
          if (id !== reqIdRef.current) return;
          if (err instanceof MapsUnavailableError) {
            setDegraded(true);
            setOpen(false);
            setItems([]);
          }
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query, lang, degraded]);

  function handleSelect(item: SuggestResult) {
    setQuery(item.text);
    setOpen(false);
    setItems([]);
    onChange({ text: item.text, lat: item.lat, lon: item.lon });
  }

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setQuery(v);
    // Любой ручной ввод сбрасывает координаты — сервер переопределит через
    // Geocoder (§7.3 шаг 2). Выбор из dropdown потом перезапишет lat/lon.
    onChange({ text: v, lat: null, lon: null });
  }

  function handleBlur() {
    if (degraded) {
      onChange({ text: query, lat: null, lon: null });
    }
  }

  return (
    <div className="relative">
      <input
        id={inputId}
        type="text"
        value={query}
        onChange={handleInput}
        onBlur={handleBlur}
        required={required}
        placeholder={t('components.addressAutocomplete.placeholder')}
        autoComplete="off"
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
      />
      {degraded && (
        <p className="mt-1 text-xs text-muted-foreground" role="status">
          {t('components.addressAutocomplete.degraded')}
        </p>
      )}
      {open && !degraded && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 z-10 mt-1 max-h-60 overflow-auto rounded-md border bg-popover shadow"
        >
          {loading && (
            <li className="px-3 py-2 text-xs text-muted-foreground">
              {t('components.addressAutocomplete.loading')}
            </li>
          )}
          {!loading && items.length === 0 && (
            <li className="px-3 py-2 text-xs text-muted-foreground">
              {t('components.addressAutocomplete.noResults')}
            </li>
          )}
          {!loading &&
            items.map((item, idx) => (
              <li
                key={`${item.text}-${idx}`}
                role="option"
                aria-selected="false"
                // onMouseDown вместо onClick: срабатывает до onBlur input'а,
                // иначе blur закрывает dropdown раньше клика.
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(item);
                }}
                className="cursor-pointer px-3 py-2 text-sm hover:bg-accent"
              >
                {item.text}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
