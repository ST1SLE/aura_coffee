import { FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  AddressAutocomplete,
  type AddressValue,
} from '@/components/AddressAutocomplete/AddressAutocomplete';
import {
  createAddress,
  updateAddress,
  AddressApiError,
  type AddressResponse,
  type AddressCreatePayload,
} from '@/api/addresses';

interface Props {
  initial?: AddressResponse;
  onSaved: (addr: AddressResponse) => void;
  onCancel: () => void;
}

export function AddressForm({ initial, onSaved, onCancel }: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru_RU' : 'en_US';

  const [address, setAddress] = useState<AddressValue>({
    text: initial?.text ?? '',
    lat: initial?.lat ?? null,
    lon: initial?.lon ?? null,
  });
  const [label, setLabel] = useState(initial?.label ?? '');
  const [apartment, setApartment] = useState(initial?.apartment ?? '');
  const [entrance, setEntrance] = useState(initial?.entrance ?? '');
  const [floor, setFloor] = useState(initial?.floor ?? '');
  const [comment, setComment] = useState(initial?.comment ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function renderError(err: unknown): string {
    if (err instanceof AddressApiError) {
      if (err.status === 409) {
        const detail = err.detail ?? '';
        // Сервер возвращает локализованный detail — используем его как есть;
        // иначе fallback на общий ключ.
        if (detail.trim().length > 0) return detail;
        return t('errors.delivery.outOfRadius');
      }
      return err.detail ?? t('errors.delivery.generic');
    }
    return t('errors.delivery.generic');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

    const payload: AddressCreatePayload = {
      text: address.text,
      lat: address.lat,
      lon: address.lon,
      label: label.trim() || null,
      apartment: apartment.trim() || null,
      entrance: entrance.trim() || null,
      floor: floor.trim() || null,
      comment: comment.trim() || null,
    };

    try {
      const saved = initial
        ? await updateAddress(initial.id, payload)
        : await createAddress(payload);
      onSaved(saved);
    } catch (err) {
      setError(renderError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-md border p-4">
      <div>
        <label className="text-xs font-medium text-muted-foreground">
          {t('pages.addresses.form.label')}
        </label>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
        />
      </div>

      <AddressAutocomplete
        value={address}
        onChange={setAddress}
        lang={lang}
        required
      />

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            {t('pages.addresses.form.apartment')}
          </label>
          <input
            type="text"
            value={apartment}
            onChange={(e) => setApartment(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            {t('pages.addresses.form.entrance')}
          </label>
          <input
            type="text"
            value={entrance}
            onChange={(e) => setEntrance(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            {t('pages.addresses.form.floor')}
          </label>
          <input
            type="text"
            value={floor}
            onChange={(e) => setFloor(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="text-xs font-medium text-muted-foreground">
          {t('pages.addresses.form.comment')}
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={2}
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
        />
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <Button type="submit" disabled={submitting || !address.text.trim()}>
          {t('pages.addresses.form.save')}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('pages.addresses.form.cancel')}
        </Button>
      </div>
    </form>
  );
}
