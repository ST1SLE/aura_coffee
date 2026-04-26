import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DAYS, type DayKey } from '@/api/admin-settings';
import type { SettingsFormState, ErrorMap, WorkingHoursDayInput } from './validation';

// START_MODULE_CONTRACT
//   PURPOSE: Render the per-day working-hours editor — checkbox to mark a day
//            closed plus open/close time inputs. Pure presentation; parent
//            owns the state.
//   SCOPE:   Used only by SettingsPage.
//   DEPENDS: react-i18next, ui Input/Label, @/api/admin-settings (DAYS), ./validation.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SectionWorkingHours - 7-day working-hours editor
// END_MODULE_MAP

interface Props {
  form: SettingsFormState;
  onDayChange: (day: DayKey, next: WorkingHoursDayInput) => void;
  errors: ErrorMap;
}

export function SectionWorkingHours({ form, onDayChange, errors }: Props) {
  const { t } = useTranslation();

  const err = (k: string) =>
    errors[k] ? (
      <p className="text-xs text-destructive" data-testid={`err-${k}`}>
        {t(`pages.settings.errors.${errors[k]}`, errors[k])}
      </p>
    ) : null;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{t('pages.settings.sections.working_hours')}</h2>
      <div className="space-y-3">
        {DAYS.map((day) => {
          const row = form.working_hours[day];
          const dayLabel = t(`pages.settings.days.${day}`);
          const rowErr =
            errors[`working_hours.${day}.open`] || errors[`working_hours.${day}.close`];
          return (
            <div
              key={day}
              className="grid grid-cols-[6rem_auto_1fr_1fr] items-center gap-3"
              data-testid={`wh-row-${day}`}
            >
              <div className="font-medium">{dayLabel}</div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={row.closed}
                  onChange={(e) =>
                    onDayChange(day, {
                      closed: e.target.checked,
                      open: e.target.checked ? '' : row.open || '09:00',
                      close: e.target.checked ? '' : row.close || '22:00',
                    })
                  }
                  data-testid={`wh-closed-${day}`}
                />
                <span>{t('pages.settings.closed')}</span>
              </label>
              {row.closed ? (
                <>
                  <div />
                  <div />
                </>
              ) : (
                <>
                  <div>
                    <Label className="sr-only" htmlFor={`wh-${day}-open`}>
                      {t('pages.settings.fields.open')}
                    </Label>
                    <Input
                      id={`wh-${day}-open`}
                      type="time"
                      value={row.open}
                      onChange={(e) =>
                        onDayChange(day, { ...row, open: e.target.value })
                      }
                      data-testid={`wh-open-${day}`}
                    />
                  </div>
                  <div>
                    <Label className="sr-only" htmlFor={`wh-${day}-close`}>
                      {t('pages.settings.fields.close')}
                    </Label>
                    <Input
                      id={`wh-${day}-close`}
                      type="time"
                      value={row.close}
                      onChange={(e) =>
                        onDayChange(day, { ...row, close: e.target.value })
                      }
                      data-testid={`wh-close-${day}`}
                    />
                  </div>
                </>
              )}
              {rowErr && <div className="col-span-4">{err(`working_hours.${day}.open`) || err(`working_hours.${day}.close`)}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
