import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { AvailableTab } from '@/pages/Courier/AvailableTab';
import { MineTab } from '@/pages/Courier/MineTab';

// START_MODULE_CONTRACT
//   PURPOSE: Courier index page — two tabs ('available', 'mine') switching
//            between the public delivery feed and the courier's claimed assignments.
//   SCOPE:   Mounted at /courier under CourierShell.
//   DEPENDS: react, react-i18next, @/lib/utils, sibling AvailableTab + MineTab.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (courier views),
//            INV-002, INV-010 (courier sees only assignments).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CourierPage - tablist toggling AvailableTab vs MineTab
// END_MODULE_MAP

type TabKey = 'available' | 'mine';

// START_CONTRACT: CourierPage
//   PURPOSE: Render the courier tab switcher and mount the active tab's
//            content. Tab state is local; no URL persistence.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: none directly; the selected tab triggers its own data fetches.
//   LINKS:   INV-002, INV-010.
// END_CONTRACT: CourierPage
export function CourierPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>('available');

  return (
    <div className="mx-auto w-full max-w-2xl flex flex-col gap-4">
      <div
        role="tablist"
        aria-label="courier-tabs"
        className="flex gap-2 p-1 bg-muted rounded-full"
      >
        <TabButton
          active={tab === 'available'}
          onClick={() => setTab('available')}
          label={t('courier.tabs.available')}
        />
        <TabButton
          active={tab === 'mine'}
          onClick={() => setTab('mine')}
          label={t('courier.tabs.mine')}
        />
      </div>
      <div>{tab === 'available' ? <AvailableTab /> : <MineTab />}</div>
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  label: string;
}

function TabButton({ active, onClick, label }: TabButtonProps) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        'flex-1 min-h-12 rounded-full px-4 text-sm font-medium transition-colors',
        active
          ? 'bg-primary text-primary-foreground shadow'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {label}
    </button>
  );
}
