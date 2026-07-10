import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, Users } from "lucide-react";

import { useAuth } from "@/auth/AuthContext";
import { ThemeToggle } from "@/components/ThemeToggle";

// Barra superiore condivisa: logo/nome (link alla dashboard), utente e logout.
export function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accountOpen) return;

    function onPointerDown(event: PointerEvent) {
      if (accountRef.current && !accountRef.current.contains(event.target as Node)) {
        setAccountOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setAccountOpen(false);
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [accountOpen]);

  async function onLogout() {
    // Usciamo prima dalla route protetta e azzeriamo l'eventuale destinazione
    // salvata da RequireAuth, così la sessione successiva non eredita l'incidente.
    navigate("/login", { replace: true, state: null });
    await logout();
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <img src="/Debrief-Light.png" alt="" className="h-6 dark:hidden" />
          <img src="/Debrief-Dark.png" alt="" className="hidden h-6 dark:block" />
          Debrief
        </Link>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          {user && (
            <div ref={accountRef} className="relative">
              <button
                type="button"
                onClick={() => setAccountOpen((open) => !open)}
                aria-label="Apri menu account"
                aria-haspopup="menu"
                aria-expanded={accountOpen}
                className={`flex h-10 w-10 items-center justify-center gap-2 rounded-md p-1 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:w-auto sm:justify-start sm:pr-2.5 ${accountOpen ? "bg-accent text-accent-foreground" : ""}`}
              >
                <Avatar username={user.username} />
                <span className="hidden min-w-0 text-left leading-tight sm:block">
                  <span className="block max-w-32 truncate text-sm font-medium">
                    {user.username}
                  </span>
                  <span className="block max-w-32 truncate text-xs text-muted-foreground">
                    {user.team_name}
                  </span>
                </span>
                <ChevronDown
                  className={`hidden h-4 w-4 text-muted-foreground transition-transform sm:block ${accountOpen ? "rotate-180" : ""}`}
                />
              </button>

              {accountOpen && (
                <div
                  role="menu"
                  className="absolute right-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-lg border bg-background p-1.5 text-foreground shadow-xl"
                >
                  <div className="flex items-center gap-3 px-2.5 py-2.5">
                    <Avatar username={user.username} large />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{user.username}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
                        <Users className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{user.team_name}</span>
                      </p>
                    </div>
                  </div>
                  <div className="my-1 border-t" />
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => void onLogout()}
                    className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10 focus-visible:bg-destructive/10 focus-visible:outline-none"
                  >
                    <LogOut className="h-4 w-4" />
                    Esci dall’account
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function Avatar({ username, large = false }: { username: string; large?: boolean }) {
  const initial = username.trim().charAt(0).toLocaleUpperCase() || "?";

  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-full bg-primary font-semibold text-primary-foreground ${large ? "h-10 w-10 text-sm" : "h-8 w-8 text-xs"}`}
    >
      {initial}
    </span>
  );
}
