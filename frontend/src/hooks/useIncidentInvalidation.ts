import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function useIncidentInvalidation(id?: string) {
  const queryClient = useQueryClient();

  return useCallback(() => {
    if (id) void queryClient.invalidateQueries({ queryKey: ["incident", id] });
    void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    void queryClient.invalidateQueries({ queryKey: ["metrics"] });
  }, [id, queryClient]);
}
