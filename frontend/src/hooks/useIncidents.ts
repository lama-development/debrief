import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { incidentsApi } from "@/lib/api"

// Lista incidenti, opzionalmente filtrata per status.
export function useIncidents(status?: string) {
  return useQuery({
    queryKey: ["incidents", status ?? "all"],
    queryFn: () => incidentsApi.list(status),
  })
}

// Crea un nuovo incidente; invalida lista e metriche al successo.
export function useCreateIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (description: string) => incidentsApi.create(description),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["incidents"] })
      qc.invalidateQueries({ queryKey: ["metrics"] })
    },
  })
}
