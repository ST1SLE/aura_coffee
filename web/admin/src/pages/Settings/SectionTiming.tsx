import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { SettingsFormState, ErrorMap } from './validation';

interface Props {
  form: SettingsFormState;
  onChange: (key: keyof SettingsFormState, value: string) => void;
  errors: ErrorMap;
}

export function SectionTiming({ form, onChange, errors }: Props) {
  const { t } = useTranslation();

  const err = (k: string) =>
    errors[k] ? (
      <p className="text-xs text-destructive" data-testid={`err-${k}`}>
        {t(`pages.settings.errors.${errors[k]}`, errors[k])}
      </p>
    ) : null;

  const min = t('pages.settings.units.minutes');

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{t('pages.settings.sections.timing')}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="default_prep_time_minutes">
            {t('pages.settings.fields.default_prep_time_minutes')} ({min})
          </Label>
          <Input
            id="default_prep_time_minutes"
            type="number"
            step="1"
            min="1"
            value={form.default_prep_time_minutes}
            onChange={(e) => onChange('default_prep_time_minutes', e.target.value)}
          />
          {err('default_prep_time_minutes')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="estimated_delivery_time_minutes">
            {t('pages.settings.fields.estimated_delivery_time_minutes')} ({min})
          </Label>
          <Input
            id="estimated_delivery_time_minutes"
            type="number"
            step="1"
            min="1"
            value={form.estimated_delivery_time_minutes}
            onChange={(e) => onChange('estimated_delivery_time_minutes', e.target.value)}
          />
          {err('estimated_delivery_time_minutes')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="auto_close_minutes">
            {t('pages.settings.fields.auto_close_minutes')} ({min})
          </Label>
          <Input
            id="auto_close_minutes"
            type="number"
            step="1"
            min="1"
            max="1440"
            value={form.auto_close_minutes}
            onChange={(e) => onChange('auto_close_minutes', e.target.value)}
          />
          {err('auto_close_minutes')}
        </div>
      </div>
    </section>
  );
}
