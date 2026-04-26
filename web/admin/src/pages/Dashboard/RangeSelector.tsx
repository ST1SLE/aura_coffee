import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import type { StatsRange } from '@/api/admin-stats';

// START_MODULE_CONTRACT
//   PURPOSE: Tablist of range buttons (today/week/month) for the dashboard.
//            Pure presentation — value/onChange controlled by parent.
//   SCOPE:   Used only by DashboardPage.
//   DEPENDS: react-i18next, @/components/ui/button, @/api/admin-stats type.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   RangeSelector - tab buttons for StatsRange selection
// END_MODULE_MAP

interface RangeSelectorProps {
  value: StatsRange;
  onChange: (next: StatsRange) => void;
}

const RANGES: StatsRange[] = ['today', 'week', 'month'];

export function RangeSelector({ value, onChange }: RangeSelectorProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-2" role="tablist">
      {RANGES.map((r) => (
        <Button
          key={r}
          role="tab"
          variant={value === r ? 'default' : 'outline'}
          size="sm"
          onClick={() => onChange(r)}
          data-testid={`range-tab-${r}`}
          aria-selected={value === r}
        >
          {t(`pages.dashboard.range.${r}`)}
        </Button>
      ))}
    </div>
  );
}
