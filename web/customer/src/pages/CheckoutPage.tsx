import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  AddressAutocomplete,
  type AddressValue,
} from '@/components/AddressAutocomplete/AddressAutocomplete';
import {
  listAddresses,
  createAddress,
  type AddressResponse,
} from '@/api/addresses';
import {
  createOrder,
  OrderApiError,
  type InlineDeliveryAddress,
} from '@/api/orders';
import {
  geocode,
  MapsUnavailableError,
  type MapsLang,
} from '@/api/yandex_maps';

// START_MODULE_CONTRACT
//   PURPOSE: Checkout route page — choose pickup vs delivery, pick a saved
//            delivery address or enter a new one (with optional save), submit
//            the order, render server-localized error detail on 409 (out-of-
//            radius), and navigate to the order status page on success.
//   SCOPE:   CheckoutPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/components/ui/button,
//            @/components/AddressAutocomplete, @/api/addresses, @/api/orders,
//            @/api/yandex_maps.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 checkout;
//            INV-013 (raw address text + comment are PII, never logged);
//            INV-014 (server returns order_items snapshot; UI does not recompute).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CheckoutPage  - /checkout route with pickup/delivery + address logic
// END_MODULE_MAP

type OrderType = 'pickup' | 'delivery';

type DeliveryChoice =
  | { kind: 'saved'; address_id: string }
  | {
      kind: 'new';
      address: AddressValue;
      apartment: string;
      entrance: string;
      floor: string;
      comment: string;
      saveForFuture: boolean;
    };

type ResolvedInlineDeliveryAddress = InlineDeliveryAddress & {
  lat: number;
  lon: number;
};

type CheckoutPayload =
  | { type: 'pickup' }
  | { type: 'delivery'; delivery_address_id: string }
  | { type: 'delivery'; delivery_address: ResolvedInlineDeliveryAddress };

const emptyNew: Extract<DeliveryChoice, { kind: 'new' }> = {
  kind: 'new',
  address: { text: '', lat: null, lon: null },
  apartment: '',
  entrance: '',
  floor: '',
  comment: '',
  saveForFuture: false,
};

const inputClassName =
  'rounded-md border border-white/10 bg-background/75 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring';
const optionClassName =
  'flex min-h-12 items-center gap-3 rounded-md border border-white/10 bg-background/75 px-3 py-2 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/10';

// START_CONTRACT: CheckoutPage
//   PURPOSE: Render and orchestrate the checkout form — order type selector,
//            saved/new address picker, submit handler, and success redirect.
//   INPUTS:  none.
//   OUTPUTS: JSX — full form with pickup/delivery + saved/new address subforms.
//   SIDE_EFFECTS: HTTP listAddresses() when DELIVERY is selected; HTTP
//                 geocode() for typed inline delivery addresses without coords;
//                 createOrder() on submit; HTTP createAddress() best-effort if
//                 "save for future" is checked; navigate(`/orders/:id`) on success.
//                 INV-013 — payload contains PII, do not log raw values.
//                 INV-014 — order_items snapshot rendered server-side later.
//   LINKS:   PDD §7; AddressForm shares the same renderError pattern.
// END_CONTRACT: CheckoutPage
export function CheckoutPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang: MapsLang = i18n.language.startsWith('ru') ? 'ru_RU' : 'en_US';

  const [orderType, setOrderType] = useState<OrderType>('pickup');
  const [saved, setSaved] = useState<AddressResponse[]>([]);
  const [choice, setChoice] = useState<DeliveryChoice>(emptyNew);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (orderType !== 'delivery') return;
    listAddresses()
      .then((items) => {
        setSaved(items);
        if (items.length > 0) {
          const primary = items.find((a) => a.is_default) ?? items[0];
          setChoice({ kind: 'saved', address_id: primary.id });
        } else {
          setChoice(emptyNew);
        }
      })
      .catch(() => {
        setSaved([]);
        setChoice(emptyNew);
      });
  }, [orderType]);

  async function resolveInlineAddress(
    nextChoice: Extract<DeliveryChoice, { kind: 'new' }>,
  ): Promise<ResolvedInlineDeliveryAddress | null> {
    const text = nextChoice.address.text.trim();
    if (!text) {
      setError(t('errors.delivery.generic'));
      return null;
    }

    let resolvedText = text;
    let lat = nextChoice.address.lat;
    let lon = nextChoice.address.lon;

    if (lat === null || lon === null) {
      try {
        const resolved = await geocode(text, lang);
        if (!resolved) {
          setError(t('errors.delivery.geocodePrecision'));
          return null;
        }
        resolvedText = resolved.canonical_text || text;
        lat = resolved.lat;
        lon = resolved.lon;
      } catch (err) {
        setError(
          err instanceof MapsUnavailableError
            ? t('errors.delivery.mapsUnavailable')
            : t('errors.delivery.geocodePrecision'),
        );
        return null;
      }
    }

    return {
      text: resolvedText,
      lat,
      lon,
      apartment: nextChoice.apartment.trim() || null,
      entrance: nextChoice.entrance.trim() || null,
      floor: nextChoice.floor.trim() || null,
      comment: nextChoice.comment.trim() || null,
    };
  }

  async function buildPayload(): Promise<CheckoutPayload | null> {
    if (orderType === 'pickup') return { type: 'pickup' };
    if (choice.kind === 'saved') {
      return { type: 'delivery', delivery_address_id: choice.address_id };
    }

    const delivery_address = await resolveInlineAddress(choice);
    if (!delivery_address) return null;

    return { type: 'delivery', delivery_address };
  }

  function renderError(err: unknown): string {
    if (err instanceof OrderApiError) {
      if (err.status === 409) {
        return err.detail?.trim()
          ? err.detail
          : t('errors.delivery.outOfRadius');
      }
      return err.detail ?? t('errors.delivery.generic');
    }
    return t('errors.delivery.generic');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);

    setSubmitting(true);
    try {
      const payload = await buildPayload();
      if (!payload) return;

      const order = await createOrder(payload);

      if (
        orderType === 'delivery' &&
        choice.kind === 'new' &&
        choice.saveForFuture &&
        'delivery_address' in payload
      ) {
        const address = payload.delivery_address;
        // Сохранение — best-effort: ошибка не блокирует переход к статусу заказа.
        // label обязателен (server min_length=1, max_length=100); у checkout нет
        // отдельного поля — используем сам адрес, обрезанный до серверного лимита.
        try {
          await createAddress({
            label: address.text.slice(0, 100),
            address_text: address.text,
            lat: address.lat,
            lon: address.lon,
            apartment: address.apartment ?? null,
            entrance: address.entrance ?? null,
            floor: address.floor ?? null,
            comment: address.comment ?? null,
          });
        } catch {
          console.warn('Failed to save address for future');
        }
      }

      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError(renderError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto max-w-3xl space-y-5 px-4 py-5 md:px-6"
    >
      <div className="aura-surface rounded-lg p-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-normal">
            {t('pages.checkout.title')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('pages.checkout.description')}
          </p>
        </div>
      </div>

      <fieldset className="aura-surface-soft grid gap-2 rounded-lg p-3 sm:grid-cols-2">
        <legend className="sr-only">{t('pages.checkout.description')}</legend>
        <label className={optionClassName}>
          <input
            type="radio"
            name="order-type"
            value="pickup"
            checked={orderType === 'pickup'}
            onChange={() => setOrderType('pickup')}
          />
          {t('pages.checkout.type.pickup')}
        </label>
        <label className={optionClassName}>
          <input
            type="radio"
            name="order-type"
            value="delivery"
            checked={orderType === 'delivery'}
            onChange={() => setOrderType('delivery')}
          />
          {t('pages.checkout.type.delivery')}
        </label>
      </fieldset>

      {orderType === 'delivery' && (
        <div className="aura-surface space-y-4 rounded-lg p-4">
          {saved.length > 0 && (
            <fieldset className="space-y-2">
              <label className={optionClassName}>
                <input
                  type="radio"
                  name="delivery-choice"
                  value="saved"
                  checked={choice.kind === 'saved'}
                  onChange={() => {
                    const primary = saved.find((a) => a.is_default) ?? saved[0];
                    setChoice({ kind: 'saved', address_id: primary.id });
                  }}
                />
                {t('pages.checkout.delivery.savedAddress')}
              </label>
              <label className={optionClassName}>
                <input
                  type="radio"
                  name="delivery-choice"
                  value="new"
                  checked={choice.kind === 'new'}
                  onChange={() => setChoice(emptyNew)}
                />
                {t('pages.checkout.delivery.newAddress')}
              </label>
            </fieldset>
          )}

          {choice.kind === 'saved' && (
            <ul className="space-y-2">
              {saved.map((a) => (
                <li key={a.id}>
                  <label className="flex items-start gap-3 rounded-md border border-white/10 bg-background/75 px-3 py-2 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/10">
                    <input
                      type="radio"
                      name="saved-address"
                      value={a.id}
                      checked={choice.address_id === a.id}
                      onChange={() =>
                        setChoice({ kind: 'saved', address_id: a.id })
                      }
                    />
                    <span>
                      {a.label && (
                        <span className="font-medium">{a.label}: </span>
                      )}
                      {a.address_text}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}

          {choice.kind === 'new' && (
            <div className="space-y-3">
              <AddressAutocomplete
                value={choice.address}
                onChange={(next) => setChoice({ ...choice, address: next })}
                lang={lang}
                required
              />
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="text"
                  placeholder={t('pages.addresses.form.apartment')}
                  value={choice.apartment}
                  onChange={(e) =>
                    setChoice({ ...choice, apartment: e.target.value })
                  }
                  className={inputClassName}
                />
                <input
                  type="text"
                  placeholder={t('pages.addresses.form.entrance')}
                  value={choice.entrance}
                  onChange={(e) =>
                    setChoice({ ...choice, entrance: e.target.value })
                  }
                  className={inputClassName}
                />
                <input
                  type="text"
                  placeholder={t('pages.addresses.form.floor')}
                  value={choice.floor}
                  onChange={(e) =>
                    setChoice({ ...choice, floor: e.target.value })
                  }
                  className={inputClassName}
                />
              </div>
              <textarea
                placeholder={t('pages.addresses.form.comment')}
                value={choice.comment}
                onChange={(e) =>
                  setChoice({ ...choice, comment: e.target.value })
                }
                rows={2}
                className={`${inputClassName} w-full resize-none`}
              />
              <label className={optionClassName}>
                <input
                  type="checkbox"
                  checked={choice.saveForFuture}
                  onChange={(e) =>
                    setChoice({ ...choice, saveForFuture: e.target.checked })
                  }
                />
                {t('pages.checkout.delivery.saveForFuture')}
              </label>
            </div>
          )}
        </div>
      )}

      {error && (
        <p
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {error}
        </p>
      )}

      <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
        {t('pages.checkout.submit')}
      </Button>
    </form>
  );
}
