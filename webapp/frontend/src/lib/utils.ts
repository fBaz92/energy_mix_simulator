import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combines class names using clsx then merges Tailwind classes via tailwind-merge.
 * Canonical shadcn/ui utility. Use for conditional class composition in components.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
