import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { authApi } from "@/lib/api";

export function useTeams() {
  const query = useQuery({
    queryKey: ["teams"],
    queryFn: authApi.teams,
    staleTime: Infinity,
  });
  const teams = useMemo(() => query.data ?? [], [query.data]);
  const namesById = useMemo(() => new Map(teams.map((team) => [team.id, team.name])), [teams]);
  const teamName = useCallback((teamId: string) => namesById.get(teamId) ?? teamId, [namesById]);

  return { ...query, teams, teamName };
}
