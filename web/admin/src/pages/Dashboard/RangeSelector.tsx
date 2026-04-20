import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import type { StatsRange } from '@/api/admin-stats';

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
