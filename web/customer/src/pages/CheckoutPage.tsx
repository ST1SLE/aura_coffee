import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';
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
  estimateOrder,
  OrderApiError,
  type CheckoutEstimateResponse,
  type CheckoutOptions,
  type CreateOrderPayload,
  type InlineDeliveryAddress,
  type MinimumDeliveryAmountDetail,
  type OrderingPausedDetail,
} from '@/api/orders';
import {
  geocode,
  MapsUnavailableError,
  type MapsLang,
} from '@/api/yandex_maps';

function isMinimumDeliveryAmountDetail(
  detail: unknown,
): detail is MinimumDeliveryAmountDetail {
  const maybe = detail as Partial<MinimumDeliveryAmountDetail> | null;
  return (
    typeof detail === 'object' &&
    detail !== null &&
    maybe?.code === 'minimum_delivery_amount' &&
    typeof maybe.subtotal === 'number' &&
    typeof maybe.min_delivery_amount === 'number'
  );
}

function isOrderingPausedDetail(detail: unknown): detail is OrderingPausedDetail {
  const maybe = detail as Partial<OrderingPausedDetail> | null;
  return (
    typeof detail === 'object' &&
    detail !== null &&
    maybe?.code === 'ordering_paused'
  );
}

function isOrderingPausedError(err: unknown): boolean {
  return err instanceof OrderApiError && isOrderingPausedDetail(err.detail);
}

function isReadableServerDetail(detail: string): boolean {
  const text = detail.trim();
  if (!text) return false;
  return !(
    /subtotal\s+\d+\s+below\s+min_delivery_amount/i.test(text) ||
    /\b[a-z]+(?:_[a-z0-9]+){1,}\b/.test(text) ||
    text.startsWith('[') ||
    text.startsWith('{') ||
    /^HTTP\s+\d+/i.test(text)
  );
}

function parseLegacyMinimumDeliveryDetail(
  detail: string,
): MinimumDeliveryAmountDetail | null {
  try {
    const parsed = JSON.parse(detail) as unknown;
    if (isMinimumDeliveryAmountDetail(parsed)) return parsed;
  } catch {
    // Plain-text server details are handled below.
  }

  const match = detail.match(
    /subtotal\s+(\d+)\s+below\s+min_delivery_amount\s+(\d+)/i,
  );
  if (!match) return null;
  return {
    code: 'minimum_delivery_amount',
    subtotal: Number(match[1]),
    min_delivery_amount: Number(match[2]),
  };
}

// START_MODULE_CONTRACT
//   PURPOSE: Checkout route page — choose pickup vs delivery, pick a saved
//            delivery address or enter a new one (with optional save), collect
//            promo/points/requested-time inputs, render server-owned estimate
//            totals, submit the order, render server-localized error detail on
//            409, and navigate to the order status page on success.
//   SCOPE:   CheckoutPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/components/ui/button,
//            @/components/AddressAutocomplete, @/api/addresses, @/api/orders,
//            @/api/yandex_maps, @/lib/formatPrice.
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
  'rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background';
const optionClassName =
  'font-display flex min-h-12 items-center gap-3 rounded-md border border-border/70 bg-card px-3 py-2 text-sm font-semibold transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/10';

type TimeMode = 'asap' | 'scheduled';

// START_CONTRACT: CheckoutPage
//   PURPOSE: Render and orchestrate the checkout form — order type selector,
//            saved/new address picker, promo/points/requested-time controls,
//            server estimate, submit handler, and success redirect.
//   INPUTS:  none.
//   OUTPUTS: JSX — full form with pickup/delivery + saved/new address subforms.
//   SIDE_EFFECTS: HTTP listAddresses() when DELIVERY is selected; HTTP
//                 geocode() for typed inline delivery addresses without coords;
//                 estimateOrder() for server-owned totals; createOrder() on
//                 submit; HTTP createAddress() best-effort if "save for future"
//                 is checked; navigate(`/orders/:id`) on success.
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
  const [promocodeCode, setPromocodeCode] = useState('');
  const [pointsToUse, setPointsToUse] = useState('');
  const [timeMode, setTimeMode] = useState<TimeMode>('asap');
  const [scheduledTime, setScheduledTime] = useState('');
  const [estimate, setEstimate] = useState<CheckoutEstimateResponse | null>(
    null,
  );
  const [estimating, setEstimating] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [orderingPaused, setOrderingPaused] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

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

  const renderError = useCallback(
    (err: unknown): string => {
      if (err instanceof OrderApiError) {
        if (isOrderingPausedDetail(err.detail)) {
          return t('errors.delivery.orderingPaused');
        }
        const minimumDetail =
          typeof err.detail === 'string'
            ? parseLegacyMinimumDeliveryDetail(err.detail)
            : err.detail;
        if (isMinimumDeliveryAmountDetail(minimumDetail)) {
          return t('errors.delivery.minimumAmount', {
            min: formatPrice(minimumDetail.min_delivery_amount, i18n.language),
            subtotal: formatPrice(minimumDetail.subtotal, i18n.language),
          });
        }
        if (err.status === 409) {
          if (
            typeof err.detail === 'string' &&
            isReadableServerDetail(err.detail)
          ) {
            return err.detail;
          }
          return t('errors.delivery.outOfRadius');
        }
        if (
          typeof err.detail === 'string' &&
          isReadableServerDetail(err.detail)
        ) {
          return err.detail;
        }
        return t('errors.delivery.generic');
      }
      return t('errors.delivery.generic');
    },
    [i18n.language, t],
  );

  const checkoutOptions = useMemo<CheckoutOptions>(() => {
    const options: CheckoutOptions = {};
    const code = promocodeCode.trim().toUpperCase();
    const parsedPoints = Number.parseInt(pointsToUse, 10);

    if (code) options.promocode_code = code;
    if (Number.isFinite(parsedPoints) && parsedPoints > 0) {
      options.points_to_use = parsedPoints;
    }
    if (timeMode === 'scheduled' && scheduledTime) {
      const requested = new Date(scheduledTime);
      if (!Number.isNaN(requested.getTime())) {
        options.requested_time = requested.toISOString();
      }
    }

    return options;
  }, [promocodeCode, pointsToUse, scheduledTime, timeMode]);

  const estimatePayload = useMemo<CreateOrderPayload | null>(() => {
    if (orderType === 'pickup') return { type: 'pickup', ...checkoutOptions };
    if (choice.kind === 'saved') {
      return {
        type: 'delivery',
        delivery_address_id: choice.address_id,
        ...checkoutOptions,
      };
    }

    const text = choice.address.text.trim();
    if (!text || choice.address.lat === null || choice.address.lon === null) {
      return null;
    }
    return {
      type: 'delivery',
      delivery_address: {
        text,
        lat: choice.address.lat,
        lon: choice.address.lon,
        apartment: choice.apartment.trim() || null,
        entrance: choice.entrance.trim() || null,
        floor: choice.floor.trim() || null,
        comment: choice.comment.trim() || null,
      },
      ...checkoutOptions,
    };
  }, [checkoutOptions, choice, orderType]);

  useEffect(() => {
    if (!estimatePayload) {
      setEstimate(null);
      setEstimateError(null);
      setEstimating(false);
      setOrderingPaused(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setEstimating(true);
      estimateOrder(estimatePayload)
        .then((next) => {
          if (cancelled) return;
          setEstimate(next);
          setEstimateError(null);
          setOrderingPaused(false);
        })
        .catch((err) => {
          if (cancelled) return;
          setEstimate(null);
          setEstimateError(renderError(err));
          setOrderingPaused(isOrderingPausedError(err));
        })
        .finally(() => {
          if (!cancelled) setEstimating(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [estimatePayload, renderError]);

  const formattedReadyAt = useMemo(() => {
    if (!estimate?.estimated_ready_at) return null;
    return new Intl.DateTimeFormat(i18n.language, {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    }).format(new Date(estimate.estimated_ready_at));
  }, [estimate?.estimated_ready_at, i18n.language]);

  async function buildPayload(): Promise<CreateOrderPayload | null> {
    if (orderType === 'pickup') return { type: 'pickup', ...checkoutOptions };
    if (choice.kind === 'saved') {
      return {
        type: 'delivery',
        delivery_address_id: choice.address_id,
        ...checkoutOptions,
      };
    }

    const delivery_address = await resolveInlineAddress(choice);
    if (!delivery_address) return null;

    return { type: 'delivery', delivery_address, ...checkoutOptions };
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
          if (
            address.lat !== undefined &&
            address.lat !== null &&
            address.lon !== undefined &&
            address.lon !== null
          ) {
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
          }
        } catch {
          console.warn('Failed to save address for future');
        }
      }

      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError(renderError(err));
      setOrderingPaused(isOrderingPausedError(err));
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
                  <label className={optionClassName}>
                    <input
                      type="radio"
                      name="saved-address"
                      value={a.id}
                      checked={choice.address_id === a.id}
                      onChange={() =>
                        setChoice({ kind: 'saved', address_id: a.id })
                      }
                    />
                    <span className="min-w-0">
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

      <div className="aura-surface space-y-4 rounded-lg p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">
              {t('pages.checkout.promocode')}
            </span>
            <input
              type="text"
              value={promocodeCode}
              onChange={(e) => setPromocodeCode(e.target.value)}
              className={`${inputClassName} w-full uppercase`}
              autoComplete="off"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">
              {t('pages.checkout.points')}
            </span>
            <input
              type="number"
              min={0}
              step={1}
              value={pointsToUse}
              onChange={(e) => setPointsToUse(e.target.value)}
              className={`${inputClassName} w-full`}
              inputMode="numeric"
            />
          </label>
        </div>

        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="sr-only">{t('pages.checkout.time.title')}</legend>
          <label className={optionClassName}>
            <input
              type="radio"
              name="checkout-time"
              value="asap"
              checked={timeMode === 'asap'}
              onChange={() => setTimeMode('asap')}
            />
            {t('pages.checkout.time.asap')}
          </label>
          <label className={optionClassName}>
            <input
              type="radio"
              name="checkout-time"
              value="scheduled"
              checked={timeMode === 'scheduled'}
              onChange={() => setTimeMode('scheduled')}
            />
            {t('pages.checkout.time.scheduled')}
          </label>
        </fieldset>

        {timeMode === 'scheduled' && (
          <input
            type="datetime-local"
            value={scheduledTime}
            onChange={(e) => setScheduledTime(e.target.value)}
            className={`${inputClassName} w-full`}
          />
        )}
      </div>

      {(estimate || estimating || estimateError) && (
        <div className="aura-surface-soft rounded-lg p-4" aria-live="polite">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-base font-semibold">
              {t('pages.checkout.estimate.title')}
            </h2>
            {estimating && (
              <span className="text-xs text-muted-foreground">
                {t('pages.checkout.estimate.refreshing')}
              </span>
            )}
          </div>

          {estimateError && (
            <p className="mt-2 text-sm text-destructive">{estimateError}</p>
          )}

          {estimate && (
            <dl className="mt-3 grid gap-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt>{t('pages.checkout.estimate.subtotal')}</dt>
                <dd className="aura-numeric">
                  {formatPrice(estimate.subtotal, i18n.language)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>{t('pages.checkout.estimate.discount')}</dt>
                <dd className="aura-numeric">
                  {formatPrice(estimate.discount_amount, i18n.language)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>{t('pages.checkout.estimate.pointsUsed')}</dt>
                <dd className="aura-numeric">{estimate.points_used}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>{t('pages.checkout.estimate.deliveryFee')}</dt>
                <dd className="aura-numeric">
                  {formatPrice(estimate.delivery_fee, i18n.language)}
                </dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-border/70 pt-2 font-semibold">
                <dt>{t('pages.checkout.estimate.total')}</dt>
                <dd className="aura-numeric text-primary">
                  {formatPrice(estimate.total, i18n.language)}
                </dd>
              </div>
              <div className="flex justify-between gap-4 text-muted-foreground">
                <dt>{t('pages.checkout.estimate.accrual')}</dt>
                <dd className="aura-numeric">{estimate.estimated_accrual}</dd>
              </div>
              {formattedReadyAt && (
                <div className="flex justify-between gap-4 text-muted-foreground">
                  <dt>{t('pages.checkout.estimate.readyAt')}</dt>
                  <dd className="aura-numeric">{formattedReadyAt}</dd>
                </div>
              )}
              {orderType === 'delivery' && estimate.free_delivery_remaining > 0 && (
                <div className="text-muted-foreground">
                  {t('pages.checkout.estimate.freeRemaining', {
                    amount: formatPrice(
                      estimate.free_delivery_remaining,
                      i18n.language,
                    ),
                  })}
                </div>
              )}
            </dl>
          )}
        </div>
      )}

      {error && (
        <p
          ref={errorRef}
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
          tabIndex={-1}
        >
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={submitting || orderingPaused}
        className="w-full sm:w-auto"
      >
        {t('pages.checkout.submit')}
      </Button>
    </form>
  );
}
