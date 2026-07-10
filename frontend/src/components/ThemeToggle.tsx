import { useState } from "react";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

// Pulsante che alterna tema chiaro/scuro. Aggiunge/rimuove la classe .dark su
// <html> (che attiva il blocco .dark di index.css) e ricorda la scelta in
// localStorage. Lo stato iniziale lo legge dalla classe già impostata dallo
// script anti-flicker in index.html.
export function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label="Cambia tema">
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
