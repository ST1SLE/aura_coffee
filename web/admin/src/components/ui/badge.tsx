import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// START_MODULE_CONTRACT
//   PURPOSE: shadcn/ui Badge primitive — small colored pill used for statuses
//            (order status, user status, promo state). Pure presentation.
//   SCOPE:   Wrapped by domain-specific badges (StatusBadge, UserStatusBadge, StateChip).
//   DEPENDS: react, class-variance-authority, @/lib/utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Badge         - styled <div> with variant prop
//   badgeVariants - cva config (default/secondary/destructive/outline/warning/muted)
//   BadgeProps    - prop type combining HTMLDiv attrs with VariantProps
// END_MODULE_MAP

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring/25',
  {
    variants: {
      variant: {
        default:
          'border-success/20 bg-success/10 text-success hover:bg-success/20',
        secondary: 'border-info/20 bg-info/10 text-info hover:bg-info/20',
        destructive:
          'border-destructive/20 bg-destructive/10 text-destructive hover:bg-destructive/20',
        outline: 'border-border bg-card text-foreground',
        warning:
          'border-warning-foreground/15 bg-warning text-warning-foreground',
        muted: 'border-border/70 bg-muted text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
