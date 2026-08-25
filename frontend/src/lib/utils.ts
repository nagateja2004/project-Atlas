import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting a caller's utility override the component default.
 *
 * A plain join is not enough: the shared field styles carry `w-full`, so a
 * caller passing `w-56` produced `"w-full w-56"` and Tailwind's stylesheet
 * order decided the winner rather than the caller. That silently forced the
 * header select to full width and wrapped the header onto three rows.
 */
export function cn(...values: ClassValue[]) {
  return twMerge(clsx(values));
}
