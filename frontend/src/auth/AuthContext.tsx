import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { authApi, getAuthToken, setAuthToken, setUnauthorizedHandler } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, teamId: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => Boolean(getAuthToken()));

  // Ripristina la sessione e registra il reset globale sui 401.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      setUser(null);
      queryClient.clear();
    });

    const token = getAuthToken();
    if (token)
      authApi
        .me()
        .then(setUser)
        .catch(() => {
          setAuthToken(null);
          setUser(null);
        })
        .finally(() => setLoading(false));

    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  async function login(username: string, password: string) {
    const { token } = await authApi.login(username, password);
    setAuthToken(token);
    const me = await authApi.me();
    queryClient.clear();
    setUser(me);
  }

  async function register(username: string, password: string, teamId: string) {
    const { user: newUser, token } = await authApi.register(username, password, teamId);
    setAuthToken(token);
    queryClient.clear();
    setUser(newUser);
  }

  async function logout() {
    try {
      await authApi.logout();
    } catch {
      // Il logout locale deve riuscire comunque.
    }
    setAuthToken(null);
    setUser(null);
    queryClient.clear();
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve essere usato dentro <AuthProvider>");
  return ctx;
}
