import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { SettingsFormState, ErrorMap } from './validation';

interface Props {
  form: SettingsFormState;
  onChange: (key: keyof SettingsFormState, value: string) => void;
  errors: ErrorMap;
}

export function SectionCoords({ form, onChange, errors }: Props) {
  const { t } = useTranslation();

  const err = (k: string) =>
    errors[k] ? (
      <p className="text-xs text-destructive" data-testid={`err-${k}`}>
        {t(`pages.settings.errors.${errors[k]}`, errors[k])}
      </p>
    ) : null;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{t('pages.settings.sections.coords')}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="shop_lat">{t('pages.settings.fields.shop_lat')}</Label>
          <Input
            id="shop_lat"
            type="number"
            step="0.000001"
            value={form.shop_lat}
            onChange={(e) => onChange('shop_lat', e.target.value)}
          />
          {err('shop_lat')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="shop_lon">{t('pages.settings.fields.shop_lon')}</Label>
          <Input
            id="shop_lon"
            type="number"
            step="0.000001"
            value={form.shop_lon}
            onChange={(e) => onChange('shop_lon', e.target.value)}
          />
          {err('shop_lon')}
        </div>
      </div>
    </section>
  );
}
