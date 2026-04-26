import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// START_MODULE_CONTRACT
//   PURPOSE: shadcn-style class-name combinator — merges clsx() truthy class
//            chunks and resolves Tailwind class conflicts via tailwind-merge
//            (so later utilities win). Used pervasively by ui/* components.
//   SCOPE:   cn helper.
//   DEPENDS: clsx, tailwind-merge.
//   LINKS:   shadcn/ui convention; docs/development-plan.xml M-WEB-CUSTOMER.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   cn  - (...ClassValue) => string — clsx + tailwind-merge
// END_MODULE_MAP

// START_CONTRACT: cn
//   PURPOSE: Compose conditional Tailwind class strings while letting later
//            utilities override earlier conflicting ones.
//   INPUTS:  ...inputs: ClassValue[] — clsx-compatible truthy/array/object args.
//   OUTPUTS: string — merged Tailwind class string.
//   SIDE_EFFECTS: none.
// END_CONTRACT: cn
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
