import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { SettingsFormState, ErrorMap } from './validation';

// START_MODULE_CONTRACT
//   PURPOSE: Render the "delivery" subsection — radius/min order/free threshold/
//            delivery fee inputs with localized units. Pure presentation.
//   SCOPE:   Used only by SettingsPage.
//   DEPENDS: react-i18next, ui Input/Label, ./validation types.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SectionDelivery - delivery-related setting inputs
// END_MODULE_MAP

interface Props {
  form: SettingsFormState;
  onChange: (key: keyof SettingsFormState, value: string) => void;
  errors: ErrorMap;
}

export function SectionDelivery({ form, onChange, errors }: Props) {
  const { t } = useTranslation();

  const err = (k: string) =>
    errors[k] ? (
      <p className="text-xs text-destructive" data-testid={`err-${k}`}>
        {t(`pages.settings.errors.${errors[k]}`, errors[k])}
      </p>
    ) : null;

  const rub = t('pages.settings.units.rub');
  const km = t('pages.settings.units.km');

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{t('pages.settings.sections.delivery')}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="delivery_radius_km">
            {t('pages.settings.fields.delivery_radius_km')} ({km})
          </Label>
          <Input
            id="delivery_radius_km"
            type="number"
            step="0.1"
            min="0.1"
            max="50"
            value={form.delivery_radius_km}
            onChange={(e) => onChange('delivery_radius_km', e.target.value)}
          />
          {err('delivery_radius_km')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="min_delivery_amount">
            {t('pages.settings.fields.min_delivery_amount')} ({rub})
          </Label>
          <Input
            id="min_delivery_amount"
            type="number"
            step="0.01"
            min="0"
            value={form.min_delivery_amount_rub}
            onChange={(e) => onChange('min_delivery_amount_rub', e.target.value)}
          />
          {err('min_delivery_amount')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="free_delivery_threshold">
            {t('pages.settings.fields.free_delivery_threshold')} ({rub})
          </Label>
          <Input
            id="free_delivery_threshold"
            type="number"
            step="0.01"
            min="0"
            value={form.free_delivery_threshold_rub}
            onChange={(e) => onChange('free_delivery_threshold_rub', e.target.value)}
          />
          {err('free_delivery_threshold')}
        </div>
        <div className="space-y-1">
          <Label htmlFor="delivery_fee">
            {t('pages.settings.fields.delivery_fee')} ({rub})
          </Label>
          <Input
            id="delivery_fee"
            type="number"
            step="0.01"
            min="0"
            value={form.delivery_fee_rub}
            onChange={(e) => onChange('delivery_fee_rub', e.target.value)}
          />
          {err('delivery_fee')}
        </div>
      </div>
    </section>
  );
}
