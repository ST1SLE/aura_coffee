import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { SettingsFormState, ErrorMap } from './validation';

// START_MODULE_CONTRACT
//   PURPOSE: Render operational shop-setting toggles such as ordering pause.
//            Pure presentation; SettingsPage owns form state and persistence.
//   SCOPE:   Used only by SettingsPage.
//   DEPENDS: react-i18next, ui Label/Switch, ./validation types.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §7.2 ordering pause.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SectionOperations - operator toggles including ordering_paused
// END_MODULE_MAP

interface Props {
  form: SettingsFormState;
  onOrderingPausedChange: (value: boolean) => void;
  errors: ErrorMap;
}

// START_CONTRACT: SectionOperations
//   PURPOSE: Show the ordering-paused switch that keeps menu browsing available
//            while blocking checkout/order creation server-side.
//   INPUTS:  form: SettingsFormState
//            onOrderingPausedChange: callback for checked state
//            errors: ErrorMap
//   OUTPUTS: JSX section.
//   SIDE_EFFECTS: Calls onOrderingPausedChange on switch changes only.
//   LINKS:   PDD §7.2 ordering pause, INV-002 server-side admin scope.
// END_CONTRACT: SectionOperations
export function SectionOperations({
  form,
  onOrderingPausedChange,
  errors,
}: Props) {
  const { t } = useTranslation();
  const error = errors.ordering_paused;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">
        {t('pages.settings.sections.operations')}
      </h2>
      <div className="flex items-start justify-between gap-4 rounded-md border border-border bg-card px-4 py-3">
        <div className="space-y-1">
          <Label htmlFor="ordering_paused">
            {t('pages.settings.fields.ordering_paused')}
          </Label>
          <p
            id="ordering_paused_help"
            className="text-sm text-muted-foreground"
          >
            {t('pages.settings.help.ordering_paused')}
          </p>
          {error && (
            <p
              className="text-xs text-destructive"
              data-testid="err-ordering_paused"
            >
              {t(`pages.settings.errors.${error}`, error)}
            </p>
          )}
        </div>
        <Switch
          id="ordering_paused"
          checked={form.ordering_paused}
          onCheckedChange={onOrderingPausedChange}
          aria-describedby="ordering_paused_help"
        />
      </div>
    </section>
  );
}
