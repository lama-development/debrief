import { useMutation } from "@tanstack/react-query";

import { useIncidentInvalidation } from "@/hooks/useIncidentInvalidation";
import { incidentsApi } from "@/lib/api";
import type { ClassificationOverrideRequest } from "@/lib/types";

export function useUpdateClassification(id: string) {
  const invalidate = useIncidentInvalidation(id);
  return useMutation({
    mutationFn: (body: ClassificationOverrideRequest) => incidentsApi.patchClassification(id, body),
    onSuccess: invalidate,
  });
}
