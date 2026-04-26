import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// START_MODULE_CONTRACT
//   PURPOSE: Tailwind/clsx classname helper used across all UI components.
//   SCOPE:   Single utility, the canonical shadcn/ui pattern.
//   DEPENDS: clsx, tailwind-merge.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   cn - join classnames with clsx then dedupe Tailwind variants via twMerge
// END_MODULE_MAP

// START_CONTRACT: cn
//   PURPOSE: Compose conditional classnames and merge conflicting Tailwind utilities.
//   INPUTS:  ...inputs: ClassValue[]
//   OUTPUTS: string — merged classname.
//   SIDE_EFFECTS: none.
// END_CONTRACT: cn
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
