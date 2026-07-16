import { useMutation, useQuery } from "@tanstack/react-query";

import { useIncidentInvalidation } from "@/hooks/useIncidentInvalidation";
import { incidentsApi } from "@/lib/api";

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () => incidentsApi.detail(id),
    enabled: !!id,
  });
}

export function useResolveIncident(id: string) {
  const invalidate = useIncidentInvalidation(id);
  return useMutation({
    mutationFn: (vars: { resolution_summary: string }) =>
      incidentsApi.resolve(id, vars.resolution_summary),
    onSuccess: invalidate,
  });
}

export function useReopenIncident(id: string) {
  const invalidate = useIncidentInvalidation(id);
  return useMutation({
    mutationFn: () => incidentsApi.reopen(id),
    onSuccess: invalidate,
  });
}
