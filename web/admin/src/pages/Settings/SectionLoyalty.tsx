import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { SettingsFormState, ErrorMap } from './validation';

// START_MODULE_CONTRACT
//   PURPOSE: Render the "loyalty" subsection — single loyalty_percent input
//            (0..100). Pure presentation.
//   SCOPE:   Used only by SettingsPage.
//   DEPENDS: react-i18next, ui Input/Label, ./validation types.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SectionLoyalty - loyalty_percent input with error rendering
// END_MODULE_MAP

interface Props {
  form: SettingsFormState;
  onChange: (key: keyof SettingsFormState, value: string) => void;
  errors: ErrorMap;
}

export function SectionLoyalty({ form, onChange, errors }: Props) {
  const { t } = useTranslation();

  const err = (k: string) =>
    errors[k] ? (
      <p className="text-xs text-destructive" data-testid={`err-${k}`}>
        {t(`pages.settings.errors.${errors[k]}`, errors[k])}
      </p>
    ) : null;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{t('pages.settings.sections.loyalty')}</h2>
      <div className="max-w-xs space-y-1">
        <Label htmlFor="loyalty_percent">
          {t('pages.settings.fields.loyalty_percent')} ({t('pages.settings.units.percent')})
        </Label>
        <Input
          id="loyalty_percent"
          type="number"
          step="1"
          min="0"
          max="100"
          value={form.loyalty_percent}
          onChange={(e) => onChange('loyalty_percent', e.target.value)}
        />
        {err('loyalty_percent')}
      </div>
    </section>
  );
}
