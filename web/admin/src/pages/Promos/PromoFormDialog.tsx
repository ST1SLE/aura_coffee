import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  createPromocode,
  updatePromocode,
  activatePromocode,
  deactivatePromocode,
  parseFieldErrors,
  ApiError,
} from '@/api/promocodes';
import type {
  PromocodeResponse,
  PromocodeDiscountType,
  PromocodeCreateInput,
  PromocodeUpdateInput,
} from '@/api/promocodes';

// START_MODULE_CONTRACT
//   PURPOSE: Modal dialog for creating or editing a promocode — handles
//            datetime-local↔ISO conversion, rubles↔kopecks/percent wire shape,
//            and locks code/discount fields once current_uses > 0.
//   SCOPE:   Opened by PromosPage; admin-only on the server.
//   DEPENDS: react, react-i18next, ui primitives, @/api/promocodes.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6 promocodes,
//            INV-002 (admin scope server-enforced).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PromoFormDialog - admin-only create/edit form with activate/deactivate buttons
// END_MODULE_MAP

interface Props {
  open: boolean;
  onClose: () => void;
  promo?: PromocodeResponse | null;
  onSaved: (promo: PromocodeResponse) => void;
  onError: (msg: string) => void;
}

interface FormState {
  code: string;
  discount_type: PromocodeDiscountType;
  discount_value: string; // rubles (для percent — целое)
  min_order: string; // rubles
  valid_from: string; // datetime-local
  valid_until: string; // datetime-local
  max_uses: string;
  max_uses_per_user: string;
}

const EMPTY: FormState = {
  code: '',
  discount_type: 'percent',
  discount_value: '',
  min_order: '',
  valid_from: '',
  valid_until: '',
  max_uses: '',
  max_uses_per_user: '',
};

// Конвертирует ISO-строку ("2026-04-20T10:00:00Z") в значение для input
// типа datetime-local ("2026-04-20T10:00"). Таймзона обрезается на слое UI.
function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '';
  }
}

function localInputToIso(v: string): string | null {
  if (!v) return null;
  const d = new Date(v);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

function kopecksToRubles(kopecks: number): string {
  const rubles = kopecks / 100;
  return rubles.toFixed(2).replace(/\.00$/, '');
}

function rublesToNumber(s: string): number {
  const v = parseFloat(s.replace(',', '.'));
  return isNaN(v) ? 0 : v;
}

function intOrNull(s: string): number | null {
  if (s.trim() === '') return null;
  const v = parseInt(s, 10);
  return isNaN(v) ? null : v;
}

function fromPromo(promo: PromocodeResponse): FormState {
  return {
    code: promo.code,
    discount_type: promo.discount_type,
    discount_value:
      promo.discount_type === 'percent'
        ? String(promo.discount_value)
        : kopecksToRubles(promo.discount_value),
    min_order: promo.min_order_amount ? kopecksToRubles(promo.min_order_amount) : '',
    valid_from: isoToLocalInput(promo.valid_from),
    valid_until: isoToLocalInput(promo.valid_until),
    max_uses: promo.max_uses != null ? String(promo.max_uses) : '',
    max_uses_per_user: promo.max_uses_per_user != null ? String(promo.max_uses_per_user) : '',
  };
}

// START_CONTRACT: PromoFormDialog
//   PURPOSE: Render the promo form, validate via server-side 422 (translated to
//            field-level errors), submit via createPromocode/updatePromocode, and
//            optionally trigger activate/deactivate inline on edit.
//   INPUTS:  Props { open, onClose, promo?, onSaved, onError }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: POST/PATCH/POST(activate)/POST(deactivate); 422 → field errors,
//            409 → duplicate_code field error, other → onError toast.
//   LINKS:   INV-002.
// END_CONTRACT: PromoFormDialog
export function PromoFormDialog({ open, onClose, promo, onSaved, onError }: Props) {
  const { t } = useTranslation();
  const isEdit = promo != null;
  const locked = isEdit && (promo?.current_uses ?? 0) > 0;

  const [form, setForm] = useState<FormState>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(promo ? fromPromo(promo) : EMPTY);
    setFieldErrors({});
  }, [open, promo]);

  const title = useMemo(
    () => (isEdit ? t('pages.promos.form.edit_title') : t('pages.promos.form.create_title')),
    [isEdit, t],
  );

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // Локализует error-код от сервера. Если msg не совпадает ни с одним
  // known-кодом — показывается как есть.
  function localizeFieldError(msg: string): string {
    const key = `pages.promos.errors.${msg}`;
    const localized = t(key);
    return localized === key ? msg : localized;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFieldErrors({});
    try {
      if (isEdit && promo) {
        const patch: PromocodeUpdateInput = {
          // code/discount_type/discount_value редактируемы только при uses=0
          ...(!locked && { code: form.code }),
          ...(!locked && { discount_type: form.discount_type }),
          ...(!locked && { discount_value_rubles: rublesToNumber(form.discount_value) }),
          min_order_rubles: form.min_order ? rublesToNumber(form.min_order) : null,
          valid_from: localInputToIso(form.valid_from),
          valid_until: localInputToIso(form.valid_until),
          max_uses: intOrNull(form.max_uses),
          max_uses_per_user: intOrNull(form.max_uses_per_user),
        };
        const saved = await updatePromocode(promo.id, patch);
        onSaved(saved);
      } else {
        const input: PromocodeCreateInput = {
          code: form.code,
          discount_type: form.discount_type,
          discount_value_rubles: rublesToNumber(form.discount_value),
          min_order_rubles: form.min_order ? rublesToNumber(form.min_order) : null,
          valid_from: localInputToIso(form.valid_from),
          valid_until: localInputToIso(form.valid_until),
          max_uses: intOrNull(form.max_uses),
          max_uses_per_user: intOrNull(form.max_uses_per_user),
        };
        const saved = await createPromocode(input);
        onSaved(saved);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setFieldErrors(parseFieldErrors(err));
      } else if (err instanceof ApiError && err.status === 409) {
        setFieldErrors({ code: 'duplicate_code' });
      } else if (err instanceof ApiError && err.status === 401) {
        onError(t('common.sessionExpired'));
      } else {
        onError(t('pages.promos.errors.generic'));
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleActivate() {
    if (!promo) return;
    setSaving(true);
    try {
      const saved = await activatePromocode(promo.id);
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setFieldErrors(parseFieldErrors(err));
      } else if (err instanceof ApiError && err.status === 409) {
        const body = err.body as { detail?: string } | null;
        const msg = body?.detail ?? 'generic';
        onError(localizeFieldError(msg));
      } else {
        onError(t('pages.promos.errors.generic'));
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!promo) return;
    setSaving(true);
    try {
      const saved = await deactivatePromocode(promo.id);
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onError(t('pages.promos.errors.activate_expired'));
      } else {
        onError(t('pages.promos.errors.generic'));
      }
    } finally {
      setSaving(false);
    }
  }

  const canActivate =
    isEdit &&
    promo &&
    !promo.is_active &&
    promo.state !== 'expired' &&
    promo.state !== 'exhausted';
  const canDeactivate = isEdit && promo?.is_active === true;

  const discountSuffix =
    form.discount_type === 'percent'
      ? t('pages.promos.form.discount_value_percent_suffix')
      : t('pages.promos.form.discount_value_rub_suffix');

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="promo-code">{t('pages.promos.form.code')}</Label>
            <Input
              id="promo-code"
              value={form.code}
              onChange={(e) => setField('code', e.target.value)}
              disabled={locked}
              title={locked ? t('pages.promos.locked_hint') : undefined}
              required
            />
            {fieldErrors.code && (
              <p className="text-xs text-destructive">{localizeFieldError(fieldErrors.code)}</p>
            )}
          </div>

          <fieldset
            className="space-y-1"
            disabled={locked}
            title={locked ? t('pages.promos.locked_hint') : undefined}
          >
            <Label>{t('pages.promos.form.discount_type')}</Label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="discount_type"
                  value="percent"
                  checked={form.discount_type === 'percent'}
                  onChange={() => setField('discount_type', 'percent')}
                  disabled={locked}
                />
                <span>{t('pages.promos.form.percent')}</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="discount_type"
                  value="fixed_amount"
                  checked={form.discount_type === 'fixed_amount'}
                  onChange={() => setField('discount_type', 'fixed_amount')}
                  disabled={locked}
                />
                <span>{t('pages.promos.form.fixed')}</span>
              </label>
            </div>
            {fieldErrors.discount_type && (
              <p className="text-xs text-destructive">{localizeFieldError(fieldErrors.discount_type)}</p>
            )}
          </fieldset>

          <div className="space-y-1">
            <Label htmlFor="promo-value">
              {t('pages.promos.form.discount_value')} ({discountSuffix})
            </Label>
            <Input
              id="promo-value"
              type="number"
              step={form.discount_type === 'percent' ? '1' : '0.01'}
              min="0"
              value={form.discount_value}
              onChange={(e) => setField('discount_value', e.target.value)}
              disabled={locked}
              title={locked ? t('pages.promos.locked_hint') : undefined}
              required
            />
            {fieldErrors.discount_value && (
              <p className="text-xs text-destructive">{localizeFieldError(fieldErrors.discount_value)}</p>
            )}
          </div>

          <div className="space-y-1">
            <Label htmlFor="promo-min-order">{t('pages.promos.form.min_order')}</Label>
            <Input
              id="promo-min-order"
              type="number"
              step="0.01"
              min="0"
              value={form.min_order}
              onChange={(e) => setField('min_order', e.target.value)}
            />
            {fieldErrors.min_order_amount && (
              <p className="text-xs text-destructive">{localizeFieldError(fieldErrors.min_order_amount)}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="promo-from">{t('pages.promos.form.valid_from')}</Label>
              <Input
                id="promo-from"
                type="datetime-local"
                value={form.valid_from}
                onChange={(e) => setField('valid_from', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="promo-until">{t('pages.promos.form.valid_until')}</Label>
              <Input
                id="promo-until"
                type="datetime-local"
                value={form.valid_until}
                onChange={(e) => setField('valid_until', e.target.value)}
              />
              {fieldErrors.valid_until && (
                <p className="text-xs text-destructive">{localizeFieldError(fieldErrors.valid_until)}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="promo-max">{t('pages.promos.form.max_uses')}</Label>
              <Input
                id="promo-max"
                type="number"
                min="1"
                value={form.max_uses}
                onChange={(e) => setField('max_uses', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="promo-max-per-user">{t('pages.promos.form.max_uses_per_user')}</Label>
              <Input
                id="promo-max-per-user"
                type="number"
                min="1"
                value={form.max_uses_per_user}
                onChange={(e) => setField('max_uses_per_user', e.target.value)}
              />
            </div>
          </div>

          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              {t('pages.promos.actions.cancel')}
            </Button>
            {canDeactivate && (
              <Button
                type="button"
                variant="outline"
                onClick={handleDeactivate}
                disabled={saving}
              >
                {t('pages.promos.actions.deactivate')}
              </Button>
            )}
            {canActivate && (
              <Button type="button" onClick={handleActivate} disabled={saving}>
                {t('pages.promos.actions.activate')}
              </Button>
            )}
            <Button type="submit" disabled={saving}>
              {isEdit ? t('pages.promos.actions.save') : t('pages.promos.actions.create')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
