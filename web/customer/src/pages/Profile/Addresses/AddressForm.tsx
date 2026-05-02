import { FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  AddressAutocomplete,
  type AddressValue,
} from '@/components/AddressAutocomplete/AddressAutocomplete';
import {
  geocode,
  MapsUnavailableError,
  type MapsLang,
} from '@/api/yandex_maps';
import {
  createAddress,
  updateAddress,
  AddressApiError,
  type AddressResponse,
  type AddressCreatePayload,
  type AddressUpdatePayload,
} from '@/api/addresses';

// START_MODULE_CONTRACT
//   PURPOSE: Create/edit form for a saved delivery address — wraps
//            AddressAutocomplete plus label + apartment/entrance/floor/comment
//            fields, dispatches to api/addresses createAddress or updateAddress
//            (depending on the optional `initial`), and renders localized
//            server detail on AddressApiError(409 = out-of-radius).
//   SCOPE:   AddressForm component.
//   DEPENDS: react, react-i18next, @/components/ui/button,
//            @/components/AddressAutocomplete, @/api/addresses.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 saved addresses;
//            INV-013 — every field is PII; do not log raw values.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AddressForm  - controlled create/edit form for a saved address
// END_MODULE_MAP

interface Props {
  initial?: AddressResponse;
  onSaved: (addr: AddressResponse) => void;
  onCancel: () => void;
}

const fieldClassName =
  'mt-1 w-full rounded-md border border-input bg-muted/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background';

// START_CONTRACT: AddressForm
//   PURPOSE: Render the address fields, validate required-ness in the disabled
//            state of the submit button, POST or PATCH on submit, and notify
//            parent through onSaved/onCancel.
//   INPUTS:  Props — initial?: AddressResponse (edit mode), onSaved: (addr) =>
//            void, onCancel: () => void.
//   OUTPUTS: JSX — full form.
//   SIDE_EFFECTS: HTTP createAddress() or updateAddress() on submit; throws
//                 AddressApiError handled inline. INV-013 PII handling.
//   LINKS:   PDD §7; consumed by AddressesPage create/edit modes.
// END_CONTRACT: AddressForm
export function AddressForm({ initial, onSaved, onCancel }: Props) {
  const { t, i18n } = useTranslation();
  const lang: MapsLang = i18n.language.startsWith('ru') ? 'ru_RU' : 'en_US';

  const [address, setAddress] = useState<AddressValue>({
    text: initial?.address_text ?? '',
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

  async function resolveCreateAddress(): Promise<AddressValue | null> {
    if (address.lat !== null && address.lon !== null) {
      return address;
    }

    try {
      const resolved = await geocode(address.text, lang);
      if (!resolved) {
        setError(t('errors.delivery.geocodePrecision'));
        return null;
      }
      return {
        text: resolved.canonical_text || address.text,
        lat: resolved.lat,
        lon: resolved.lon,
      };
    } catch (err) {
      setError(
        err instanceof MapsUnavailableError
          ? t('errors.delivery.mapsUnavailable')
          : t('errors.delivery.geocodePrecision'),
      );
      return null;
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);

    const sharedPayload: Omit<AddressCreatePayload, 'lat' | 'lon'> = {
      label: label.trim(),
      address_text: address.text,
      apartment: apartment.trim() || null,
      entrance: entrance.trim() || null,
      floor: floor.trim() || null,
      comment: comment.trim() || null,
    };

    setSubmitting(true);

    try {
      let saved: AddressResponse;
      if (initial) {
        const updatePayload: AddressUpdatePayload = sharedPayload;
        saved = await updateAddress(initial.id, updatePayload);
      } else {
        const resolvedAddress = await resolveCreateAddress();
        if (!resolvedAddress) {
          return;
        }
        saved = await createAddress({
          ...sharedPayload,
          address_text: resolvedAddress.text,
          lat: resolvedAddress.lat,
          lon: resolvedAddress.lon,
        });
      }
      onSaved(saved);
    } catch (err) {
      setError(renderError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="aura-surface space-y-4 rounded-lg bg-card/95 p-4"
    >
      <div>
        <label className="text-xs font-medium text-muted-foreground">
          {t('pages.addresses.form.label')}
        </label>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className={fieldClassName}
        />
      </div>

      <AddressAutocomplete
        value={address}
        onChange={setAddress}
        lang={lang}
        required
      />

      <div className="grid gap-2 sm:grid-cols-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            {t('pages.addresses.form.apartment')}
          </label>
          <input
            type="text"
            value={apartment}
            onChange={(e) => setApartment(e.target.value)}
            className={fieldClassName}
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
            className={fieldClassName}
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
            className={fieldClassName}
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
          className={fieldClassName}
        />
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-2 sm:flex">
        <Button
          type="submit"
          disabled={submitting || !address.text.trim() || !label.trim()}
          className="sm:min-w-28"
        >
          {t('pages.addresses.form.save')}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('pages.addresses.form.cancel')}
        </Button>
      </div>
    </form>
  );
}
