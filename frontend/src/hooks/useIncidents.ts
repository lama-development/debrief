import { useMutation, useQuery } from "@tanstack/react-query";

import { useIncidentInvalidation } from "@/hooks/useIncidentInvalidation";
import { incidentsApi } from "@/lib/api";

// Lista degli incidenti, eventualmente filtrata per stato.
export function useIncidents(status?: string) {
  return useQuery({
    queryKey: ["incidents", status ?? "all"],
    queryFn: () => incidentsApi.list(status),
  });
}

// Dopo la creazione aggiorna lista e metriche memorizzate nella cache.
export function useCreateIncident() {
  const invalidate = useIncidentInvalidation();
  return useMutation({
    mutationFn: (description: string) => incidentsApi.create(description),
    onSuccess: invalidate,
  });
}
