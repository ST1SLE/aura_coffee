import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import {
  getSettings,
  updateSettings,
  parseFieldErrorsDeep,
  ApiError,
  type DayKey,
} from '@/api/admin-settings';
import { SectionCoords } from './SectionCoords';
import { SectionDelivery } from './SectionDelivery';
import { SectionLoyalty } from './SectionLoyalty';
import { SectionOperations } from './SectionOperations';
import { SectionTiming } from './SectionTiming';
import { SectionWorkingHours } from './SectionWorkingHours';
import {
  formToPayload,
  isFormValid,
  responseToForm,
  validateAll,
  type SettingsFormState,
  type WorkingHoursDayInput,
} from './validation';

// START_MODULE_CONTRACT
//   PURPOSE: Admin shop-settings page — load current settings, run client-side
//            validation, submit a full ShopSettingsUpdate payload, and surface
//            FastAPI 422 server errors per-field, including ordering pause.
//   SCOPE:   Admin-only route (gated client-side via ProtectedRoute and server-
//            side via INV-002).
//   DEPENDS: react, react-i18next, @/api/admin-settings, @/components/ui/*,
//            sibling Section* components, ./validation.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §5.2, §7.2,
//            INV-002 (admin scope server-enforced).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SettingsPage - data-fetching admin form for shop settings with full validation
// END_MODULE_MAP

// START_CONTRACT: SettingsPage
//   PURPOSE: Load shop settings on mount, render six form sections, run client
//            validation, submit updates and merge server-side 422 errors into
//            the form state. Disables the Save button when nothing is dirty
//            or the form is invalid.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element (loading skeleton initially, then form).
//   SIDE_EFFECTS: GET /api/v1/admin/settings on mount; PUT on submit; notifier
//            toasts for transport errors; cancellation flag avoids stale state.
//   LINKS:   INV-002 (admin scope; 401 surfaces as session-expired toast).
// END_CONTRACT: SettingsPage
export function SettingsPage() {
  const { t } = useTranslation();
  const { notifications, notify, dismiss } = useNotifier();

  const [loading, setLoading] = useState(true);
  const [initialForm, setInitialForm] = useState<SettingsFormState | null>(null);
  const [form, setForm] = useState<SettingsFormState | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const resp = await getSettings();
        if (cancelled) return;
        const f = responseToForm(resp);
        setInitialForm(f);
        setForm(f);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 401) {
            notify(t('common.sessionExpired'), 'error');
          } else {
            notify(t('pages.settings.toast.error'), 'error');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clientErrors = useMemo(
    () => (form ? validateAll(form) : {}),
    [form],
  );

  // Сервер-ошибки (422) приоритетнее клиентских — показывают реальную причину 422.
  const errors = useMemo(
    () => ({ ...clientErrors, ...serverErrors }),
    [clientErrors, serverErrors],
  );

  const isDirty = useMemo(() => {
    if (!form || !initialForm) return false;
    return JSON.stringify(form) !== JSON.stringify(initialForm);
  }, [form, initialForm]);

  const isValid = form ? isFormValid(form) : false;

  function setField(key: keyof SettingsFormState, value: string) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    if (serverErrors[key]) {
      setServerErrors((prev) => {
        const rest = { ...prev };
        delete rest[key];
        return rest;
      });
    }
  }

  function setOrderingPaused(value: boolean) {
    setForm((prev) => (prev ? { ...prev, ordering_paused: value } : prev));
    if (serverErrors.ordering_paused) {
      setServerErrors((prev) => {
        const rest = { ...prev };
        delete rest.ordering_paused;
        return rest;
      });
    }
  }

  function setDay(day: DayKey, next: WorkingHoursDayInput) {
    setForm((prev) =>
      prev
        ? { ...prev, working_hours: { ...prev.working_hours, [day]: next } }
        : prev,
    );
    // Сбрасываем соответствующие server-errors этого дня.
    setServerErrors((prev) => {
      const next: Record<string, string> = {};
      for (const k of Object.keys(prev)) {
        if (!k.startsWith(`working_hours.${day}.`)) next[k] = prev[k];
      }
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (!isFormValid(form)) return;

    setSaving(true);
    setServerErrors({});
    try {
      const payload = formToPayload(form);
      const resp = await updateSettings(payload);
      const fresh = responseToForm(resp);
      setInitialForm(fresh);
      setForm(fresh);
      notify(t('pages.settings.toast.saved'), 'success');
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setServerErrors(parseFieldErrorsDeep(err));
      } else if (err instanceof ApiError && err.status === 401) {
        notify(t('common.sessionExpired'), 'error');
      } else {
        notify(t('pages.settings.toast.error'), 'error');
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading || !form) {
    return (
      <div className="space-y-4" data-testid="settings-loading">
        <h1 className="text-2xl font-bold">{t('pages.settings.title')}</h1>
        <div className="h-8 w-full animate-pulse rounded bg-muted" />
        <div className="h-32 w-full animate-pulse rounded bg-muted" />
        <div className="h-32 w-full animate-pulse rounded bg-muted" />
        <NotificationList notifications={notifications} onDismiss={dismiss} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t('pages.settings.title')}</h1>

      <form onSubmit={handleSubmit} className="space-y-8" noValidate>
        <SectionCoords form={form} onChange={setField} errors={errors} />
        <SectionDelivery form={form} onChange={setField} errors={errors} />
        <SectionLoyalty form={form} onChange={setField} errors={errors} />
        <SectionOperations
          form={form}
          onOrderingPausedChange={setOrderingPaused}
          errors={errors}
        />
        <SectionTiming form={form} onChange={setField} errors={errors} />
        <SectionWorkingHours form={form} onDayChange={setDay} errors={errors} />

        <div className="flex justify-end">
          <Button type="submit" disabled={!isDirty || !isValid || saving}>
            {t('pages.settings.save_button')}
          </Button>
        </div>
      </form>

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
