// Chiamate a FastAPI con token bearer e gestione centralizzata degli errori.

import type {
  ClassificationOverrideRequest,
  Incident,
  IncidentDetail,
  Metrics,
  Team,
  User,
} from "@/lib/types";

export const API_URL = "http://localhost:8000";

const TOKEN_KEY = "debrief_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// Cache in memoria sincronizzata con localStorage.
let authToken: string | null = localStorage.getItem(TOKEN_KEY);

export function getAuthToken(): string | null {
  return authToken;
}

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && authToken) headers["Authorization"] = `Bearer ${authToken}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Impossibile contattare il server. È avviato su " + API_URL + "?");
  }

  if (res.status === 401) {
    if (auth) {
      if (onUnauthorized) onUnauthorized();
      throw new ApiError(401, "Sessione scaduta. Effettua di nuovo il login.");
    }
    throw new ApiError(401, "Username o password non validi.");
  }

  if (!res.ok) {
    // Preferisce il dettaglio restituito da FastAPI.
    let detail = `Errore ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail)
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // corpo non-JSON: teniamo il messaggio generico.
    }
    throw new ApiError(res.status, detail);
  }

  // Le risposte 204 non hanno corpo.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Autenticazione
export const authApi = {
  register: (username: string, password: string, team_id: string) =>
    request<{ user: User; token: string }>("/auth/register", {
      method: "POST",
      body: { username, password, team_id },
      auth: false,
    }),
  login: (username: string, password: string) =>
    request<{ token: string }>("/auth/login", {
      method: "POST",
      body: { username, password },
      auth: false,
    }),
  me: () => request<User>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  teams: () => request<Team[]>("/auth/teams", { auth: false }),
};

// Incidenti
export const incidentsApi = {
  list: (status?: string, limit = 100) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", String(limit));
    return request<Incident[]>(`/incidents?${params.toString()}`);
  },
  create: (description: string) =>
    request<Incident>("/incidents", { method: "POST", body: { description } }),
  detail: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
  resolve: (id: string, resolution_summary: string) =>
    request<Incident>(`/incidents/${id}/resolve`, {
      method: "POST",
      body: { resolution_summary },
    }),
  reopen: (id: string) => request<Incident>(`/incidents/${id}/reopen`, { method: "POST" }),
  patchClassification: (id: string, body: ClassificationOverrideRequest) =>
    request<Incident>(`/incidents/${id}/classification`, { method: "PATCH", body }),
  addHumanSolution: (id: string, solution: string) =>
    request(`/incidents/${id}/human-solutions`, {
      method: "POST",
      body: { solution },
    }),
};

// Metriche
export const metricsApi = {
  get: () => request<Metrics>("/metrics"),
};
