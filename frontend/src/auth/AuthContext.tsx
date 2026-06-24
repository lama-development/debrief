import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

import { authApi, getAuthToken, setAuthToken, setUnauthorizedHandler } from "@/lib/api"
import type { User } from "@/lib/types"

interface AuthContextValue {
  user: User | null
  loading: boolean // true mentre validiamo un token salvato all'avvio
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // All'avvio: se c'è un token salvato, proviamo a recuperare l'utente (/auth/me).
  // Registriamo anche l'handler di 401 che pulisce lo stato di sessione.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null)
      setUser(null)
    })

    const token = getAuthToken()
    if (!token) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        // token non più valido: lo rimuoviamo silenziosamente.
        setAuthToken(null)
        setUser(null)
      })
      .finally(() => setLoading(false))

    return () => setUnauthorizedHandler(null)
  }, [])

  async function login(username: string, password: string) {
    const { token } = await authApi.login(username, password)
    setAuthToken(token)
    const me = await authApi.me()
    setUser(me)
  }

  async function register(username: string, password: string) {
    const { user: newUser, token } = await authApi.register(username, password)
    setAuthToken(token)
    setUser(newUser)
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // best-effort: anche se la chiamata fallisce, puliamo comunque lato client.
    }
    setAuthToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth deve essere usato dentro <AuthProvider>")
  return ctx
}
