import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import App from "./App.tsx"
import { AuthProvider } from "@/auth/AuthContext"
import { Toaster } from "@/components/ui/sonner"
import "./index.css"

// Un'unica istanza del QueryClient per tutta l'app (cache condivisa).
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Evita refetch aggressivi: i dati restano "freschi" 30s; niente refetch al focus.
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Nota: niente <StrictMode> di proposito. In dev raddoppia l'esecuzione degli
// effect, e qui ChatPanel ha un effect che AVVIA il triage automatico al mount:
// con StrictMode partirebbe due volte.
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  </QueryClientProvider>,
)
