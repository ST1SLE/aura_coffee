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
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
        secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive: 'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        outline: 'text-foreground',
        warning: 'border-transparent bg-yellow-100 text-yellow-800',
        muted: 'border-transparent bg-muted text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
