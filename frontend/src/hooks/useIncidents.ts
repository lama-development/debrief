import { useMutation, useQuery } from "@tanstack/react-query";

import { useIncidentInvalidation } from "@/hooks/useIncidentInvalidation";
import { incidentsApi } from "@/lib/api";

// Lista incidenti, opzionalmente filtrata per status.
export function useIncidents(status?: string) {
  return useQuery({
    queryKey: ["incidents", status ?? "all"],
    queryFn: () => incidentsApi.list(status),
  });
}

// Crea un nuovo incidente; invalida lista e metriche al successo.
export function useCreateIncident() {
  const invalidate = useIncidentInvalidation();
  return useMutation({
    mutationFn: (description: string) => incidentsApi.create(description),
    onSuccess: invalidate,
  });
}
