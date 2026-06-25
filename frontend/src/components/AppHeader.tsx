import { Link, useNavigate } from "react-router-dom"
import { LogOut } from "lucide-react"

import { useAuth } from "@/auth/AuthContext"
import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/ThemeToggle"

// Barra superiore condivisa: logo/nome (link alla dashboard), utente e logout.
export function AppHeader() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function onLogout() {
    await logout()
    navigate("/login", { replace: true })
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <img src="/Debrief-Light.png" alt="" className="h-6 dark:hidden" />
          <img src="/Debrief-Dark.png" alt="" className="h-6 hidden dark:block" />
          Debrief
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          {user && <span className="hidden sm:inline text-sm text-muted-foreground">{user.username}</span>}
          <ThemeToggle />
          <Button variant="ghost" size="icon" className="sm:w-auto sm:px-3" onClick={onLogout} aria-label="Esci">
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline ml-1.5">Esci</span>
          </Button>
        </div>
      </div>
    </header>
  )
}
