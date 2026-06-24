import { useQuery } from "@tanstack/react-query"

import { metricsApi } from "@/lib/api"

// Metriche aggregate per la dashboard (conteggi + MTTR).
export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: () => metricsApi.get(),
  })
}
