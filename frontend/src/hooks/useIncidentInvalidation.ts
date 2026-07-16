import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function useIncidentInvalidation(id?: string) {
  const queryClient = useQueryClient();

  // Una modifica all'incidente influenza dettaglio, elenco e metriche.
  return useCallback(() => {
    if (id) void queryClient.invalidateQueries({ queryKey: ["incident", id] });
    void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    void queryClient.invalidateQueries({ queryKey: ["metrics"] });
  }, [id, queryClient]);
}
