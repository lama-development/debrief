import { cn } from "@/lib/utils";
import { SEVERITY_CLASS, SEVERITY_TOOLTIP } from "@/lib/labels";
import type { Severity } from "@/lib/types";
import { Tooltip } from "@/components/ui/tooltip";

// Badge severità con colore dedicato (SEV1 rosso … SEV4 grigio).
export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity | null;
  className?: string;
}) {
  if (!severity) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full border border-dashed px-2.5 py-0.5 text-sm font-medium text-muted-foreground",
          className,
        )}
      >
        N/A
      </span>
    );
  }
  return (
    <Tooltip content={SEVERITY_TOOLTIP[severity]}>
      <span
        className={cn(
          "inline-flex cursor-help items-center rounded-full border px-2.5 py-0.5 text-sm font-semibold shadow-sm",
          SEVERITY_CLASS[severity],
          className,
        )}
      >
        {severity}
      </span>
    </Tooltip>
  );
}
