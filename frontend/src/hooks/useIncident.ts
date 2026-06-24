import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { incidentsApi } from "@/lib/api"

// Dettaglio completo di un incidente (campi + timeline + remediation + post-mortem).
export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () => incidentsApi.detail(id),
    enabled: !!id,
  })
}

// Invalida le query toccate da un'azione di lifecycle: dettaglio, lista, metriche.
function useLifecycleInvalidation(id: string) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ["incident", id] })
    qc.invalidateQueries({ queryKey: ["incidents"] })
    qc.invalidateQueries({ queryKey: ["metrics"] })
  }
}

export function useResolveIncident(id: string) {
  const invalidate = useLifecycleInvalidation(id)
  return useMutation({
    mutationFn: (vars: { resolution_summary: string; verified_solution?: string }) =>
      incidentsApi.resolve(id, vars.resolution_summary, vars.verified_solution),
    onSuccess: invalidate,
  })
}

export function useReopenIncident(id: string) {
  const invalidate = useLifecycleInvalidation(id)
  return useMutation({
    mutationFn: () => incidentsApi.reopen(id),
    onSuccess: invalidate,
  })
}
