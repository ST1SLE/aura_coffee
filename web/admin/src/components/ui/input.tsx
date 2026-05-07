import * as React from 'react';
import { cn } from '@/lib/utils';

// START_MODULE_CONTRACT
//   PURPOSE: shadcn/ui Input primitive — styled <input> with forwardRef.
//            Pure presentation.
//   SCOPE:   Used by all admin forms (settings, login, menu, promos, users adjust).
//   DEPENDS: react, @/lib/utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Input     - styled HTML input with forwardRef
//   InputProps - alias for React.InputHTMLAttributes<HTMLInputElement>
// END_MODULE_MAP

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        'flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm shadow-sm transition-[border-color,box-shadow] file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:bg-muted/70 disabled:opacity-70',
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = 'Input';

export { Input };
