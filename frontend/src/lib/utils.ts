import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// cn(): unisce classi condizionali (clsx) e risolve i conflitti Tailwind
// (tailwind-merge), es. cn("px-2", isActive && "px-4") -> "px-4". È l'helper
// standard di shadcn/ui, usato da tutte le primitive UI.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
