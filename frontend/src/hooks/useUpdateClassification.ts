import { useMutation, useQueryClient } from "@tanstack/react-query";

import { incidentsApi } from "@/lib/api";
import type { ClassificationOverrideRequest } from "@/lib/types";

export function useUpdateClassification(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ClassificationOverrideRequest) => incidentsApi.patchClassification(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["incident", id] });
      qc.invalidateQueries({ queryKey: ["incidents"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}
