import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  adjustLoyalty,
  parseAdjustError,
  ApiError,
} from '@/api/admin-users';

// START_MODULE_CONTRACT
//   PURPOSE: Inline form for an admin loyalty-balance adjustment — strict
//            integer delta, mandatory reason, surfaces server insufficient_balance
//            as a field-level error rather than a toast.
//   SCOPE:   Embedded in UserDetailDialog.
//   DEPENDS: react, react-i18next, ui primitives, @/api/admin-users.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.7,
//            INV-002 (admin scope).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoyaltyAdjustForm - admin-only loyalty-balance adjustment form
// END_MODULE_MAP

interface Props {
  userId: string;
  onSuccess: () => void;
  onNotify: (message: string, variant: 'success' | 'error') => void;
}

interface Errors {
  delta?: string;
  reason?: string;
}

// Парсит строку в целое число. Возвращает null если невалидно.
function parseIntStrict(s: string): number | null {
  const trimmed = s.trim();
  if (trimmed === '' || !/^-?\d+$/.test(trimmed)) return null;
  const n = Number(trimmed);
  return Number.isInteger(n) ? n : null;
}

// START_CONTRACT: LoyaltyAdjustForm
//   PURPOSE: Validate delta as a non-zero integer and reason as non-empty text,
//            then POST adjustLoyalty. Routes 422 insufficient_balance into the
//            field-level error map; other errors go through the parent's notify.
//   INPUTS:  Props { userId, onSuccess, onNotify }
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: POST adjustLoyalty (admin-only); 422/other errors surfaced
//            via field errors or onNotify.
//   LINKS:   INV-002.
// END_CONTRACT: LoyaltyAdjustForm
export function LoyaltyAdjustForm({ userId, onSuccess, onNotify }: Props) {
  const { t } = useTranslation();
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): {
    ok: true;
    delta: number;
    reason: string;
  } | { ok: false; errors: Errors } {
    const errs: Errors = {};
    const n = parseIntStrict(delta);
    if (n === null) errs.delta = t('pages.users.adjust.error_delta_invalid');
    else if (n === 0) errs.delta = t('pages.users.adjust.error_delta_zero');

    const r = reason.trim();
    if (r.length === 0) errs.reason = t('pages.users.adjust.error_reason_empty');
    else if (reason.length > 500)
      errs.reason = t('pages.users.adjust.error_reason_too_long');

    if (errs.delta || errs.reason) return { ok: false, errors: errs };
    return { ok: true, delta: n!, reason: r };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const result = validate();
    if (!result.ok) {
      setErrors(result.errors);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      await adjustLoyalty(userId, { delta: result.delta, reason: result.reason });
      setDelta('');
      setReason('');
      onNotify(t('pages.users.adjust.success'), 'success');
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const parsed = parseAdjustError(err);
        if (parsed === 'insufficient_balance') {
          setErrors({ delta: t('pages.users.adjust.error_insufficient') });
        } else {
          onNotify(t('pages.users.adjust.error_insufficient'), 'error');
        }
      } else {
        onNotify(t('common.error'), 'error');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h4 className="text-sm font-semibold">{t('pages.users.adjust.title')}</h4>

      <div className="space-y-1">
        <Label htmlFor="adjust-delta">
          {t('pages.users.adjust.delta_label')}
        </Label>
        <Input
          id="adjust-delta"
          data-testid="adjust-delta"
          type="text"
          inputMode="numeric"
          value={delta}
          placeholder={t('pages.users.adjust.delta_hint')}
          onChange={(e) => setDelta(e.target.value)}
        />
        {errors.delta && (
          <p
            data-testid="adjust-error-delta"
            className="text-xs text-destructive"
          >
            {errors.delta}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="adjust-reason">
          {t('pages.users.adjust.reason_label')}
        </Label>
        <textarea
          id="adjust-reason"
          data-testid="adjust-reason"
          value={reason}
          maxLength={1000}
          rows={3}
          placeholder={t('pages.users.adjust.reason_placeholder')}
          onChange={(e) => setReason(e.target.value)}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        {errors.reason && (
          <p
            data-testid="adjust-error-reason"
            className="text-xs text-destructive"
          >
            {errors.reason}
          </p>
        )}
      </div>

      <div className="flex justify-end">
        <Button
          type="submit"
          data-testid="adjust-submit"
          disabled={submitting}
        >
          {t('pages.users.adjust.submit')}
        </Button>
      </div>
    </form>
  );
}
