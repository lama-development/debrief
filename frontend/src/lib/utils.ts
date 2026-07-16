import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Unisce classi condizionali e risolve i conflitti Tailwind.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
