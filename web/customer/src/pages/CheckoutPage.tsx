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
  type CreateOrderPayload,
  type InlineDeliveryAddress,
} from '@/api/orders';

type OrderType = 'PICKUP' | 'DELIVERY';

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

const emptyNew: Extract<DeliveryChoice, { kind: 'new' }> = {
  kind: 'new',
  address: { text: '', lat: null, lon: null },
  apartment: '',
  entrance: '',
  floor: '',
  comment: '',
  saveForFuture: false,
};

export function CheckoutPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language.startsWith('ru') ? 'ru_RU' : 'en_US';

  const [orderType, setOrderType] = useState<OrderType>('PICKUP');
  const [saved, setSaved] = useState<AddressResponse[]>([]);
  const [choice, setChoice] = useState<DeliveryChoice>(emptyNew);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (orderType !== 'DELIVERY') return;
    listAddresses()
      .then((items) => {
        setSaved(items);
        if (items.length > 0) {
          const primary = items.find((a) => a.is_primary) ?? items[0];
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

  function buildPayload(): CreateOrderPayload | null {
    if (orderType === 'PICKUP') return { type: 'PICKUP' };
    if (choice.kind === 'saved') {
      return { type: 'DELIVERY', delivery_address_id: choice.address_id };
    }
    if (!choice.address.text.trim()) {
      setError(t('errors.delivery.generic'));
      return null;
    }
    const delivery_address: InlineDeliveryAddress = {
      text: choice.address.text,
      lat: choice.address.lat,
      lon: choice.address.lon,
      apartment: choice.apartment.trim() || null,
      entrance: choice.entrance.trim() || null,
      floor: choice.floor.trim() || null,
      comment: choice.comment.trim() || null,
    };
    return { type: 'DELIVERY', delivery_address };
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
    const payload = buildPayload();
    if (!payload) return;

    setSubmitting(true);
    try {
      const order = await createOrder(payload);

      if (
        orderType === 'DELIVERY' &&
        choice.kind === 'new' &&
        choice.saveForFuture
      ) {
        // Сохранение — best-effort: ошибка не блокирует переход к статусу заказа.
        try {
          await createAddress({
            text: choice.address.text,
            lat: choice.address.lat,
            lon: choice.address.lon,
            apartment: choice.apartment.trim() || null,
            entrance: choice.entrance.trim() || null,
            floor: choice.floor.trim() || null,
            comment: choice.comment.trim() || null,
          });
        } catch (saveErr) {
          console.warn('Failed to save address for future:', saveErr);
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
    <form onSubmit={handleSubmit} className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-bold">{t('pages.checkout.title')}</h1>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-muted-foreground">
          {t('pages.checkout.description')}
        </legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="order-type"
            value="PICKUP"
            checked={orderType === 'PICKUP'}
            onChange={() => setOrderType('PICKUP')}
          />
          {t('pages.checkout.type.pickup')}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="order-type"
            value="DELIVERY"
            checked={orderType === 'DELIVERY'}
            onChange={() => setOrderType('DELIVERY')}
          />
          {t('pages.checkout.type.delivery')}
        </label>
      </fieldset>

      {orderType === 'DELIVERY' && (
        <div className="space-y-3 rounded-md border p-4">
          {saved.length > 0 && (
            <fieldset className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="delivery-choice"
                  value="saved"
                  checked={choice.kind === 'saved'}
                  onChange={() => {
                    const primary = saved.find((a) => a.is_primary) ?? saved[0];
                    setChoice({ kind: 'saved', address_id: primary.id });
                  }}
                />
                {t('pages.checkout.delivery.savedAddress')}
              </label>
              <label className="flex items-center gap-2 text-sm">
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
                  <label className="flex items-start gap-2 text-sm">
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
                      {a.text}
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
                onChange={(next) =>
                  setChoice({ ...choice, address: next })
                }
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
                  className="rounded-md border px-3 py-2 text-sm"
                />
                <input
                  type="text"
                  placeholder={t('pages.addresses.form.entrance')}
                  value={choice.entrance}
                  onChange={(e) =>
                    setChoice({ ...choice, entrance: e.target.value })
                  }
                  className="rounded-md border px-3 py-2 text-sm"
                />
                <input
                  type="text"
                  placeholder={t('pages.addresses.form.floor')}
                  value={choice.floor}
                  onChange={(e) =>
                    setChoice({ ...choice, floor: e.target.value })
                  }
                  className="rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <textarea
                placeholder={t('pages.addresses.form.comment')}
                value={choice.comment}
                onChange={(e) =>
                  setChoice({ ...choice, comment: e.target.value })
                }
                rows={2}
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
              <label className="flex items-center gap-2 text-sm">
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
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <Button type="submit" disabled={submitting}>
        {t('pages.checkout.submit')}
      </Button>
    </form>
  );
}
