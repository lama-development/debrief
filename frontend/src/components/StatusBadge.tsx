import { cn } from "@/lib/utils";
import { STATUS_CLASS, STATUS_LABEL } from "@/lib/labels";
import type { IncidentStatus } from "@/lib/types";

// Badge stato con colore + etichetta in italiano.
export function StatusBadge({ status, className }: { status: IncidentStatus; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-medium shadow-sm",
        STATUS_CLASS[status] ??
          "border border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-500/30 dark:bg-slate-500/15 dark:text-slate-200",
        className,
      )}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
