import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { ApiError, authApi } from "@/lib/api";
import type { Team } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as LocationState | null)?.from?.pathname ?? "/";

  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [teamId, setTeamId] = useState("");
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authApi
      .teams()
      .then(setTeams)
      .catch(() => setError("Impossibile caricare i team."));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(username, password);
        navigate(from, { replace: true });
      } else {
        await register(username, password, teamId);
        // Un account appena creato può non avere accesso alla pagina richiesta
        // dalla sessione precedente: parte sempre dalla propria dashboard.
        navigate("/", { replace: true });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore inatteso. Riprova.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white p-4 dark:bg-black">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <img src="/favicon.svg" alt="" className="mx-auto mb-2 h-12 w-12" />
          <CardTitle className="text-2xl">Debrief</CardTitle>
          <CardDescription>
            {mode === "login" ? "Accedi alla piattaforma" : "Crea un nuovo account"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            {mode === "register" && (
              <div className="space-y-2">
                <Label htmlFor="team">Team</Label>
                <Select
                  id="team"
                  value={teamId}
                  onChange={setTeamId}
                  options={teams.map((team) => ({ value: team.id, label: team.name }))}
                  placeholder="Seleziona il tuo team…"
                  ariaLabel="Seleziona il tuo team"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
              />
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button
              type="submit"
              className="w-full"
              disabled={submitting || (mode === "register" && !teamId)}
            >
              {submitting ? "Attendi…" : mode === "login" ? "Accedi" : "Registrati"}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            {mode === "login" ? "Non hai un account?" : "Hai già un account?"}{" "}
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
            >
              {mode === "login" ? "Registrati" : "Accedi"}
            </button>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
