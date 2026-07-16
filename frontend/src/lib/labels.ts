// Etichette in italiano e classi colore per stati/severità.
// Centralizzate qui così badge, tabelle e filtri restano coerenti.

import type { IncidentStatus, Severity } from "@/lib/types";

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  open: "Da classificare", // non ancora classificato dal triage (o in attesa di dettagli)
  active: "In corso",
  resolved: "Risolto",
};

export const STATUS_CLASS: Record<IncidentStatus, string> = {
  open: "border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-200",
  active:
    "border border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/15 dark:text-sky-200",
  resolved:
    "border border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-200",
};

export const SEVERITY_TOOLTIP: Record<Severity, string> = {
  SEV1: "Critico",
  SEV2: "Alto",
  SEV3: "Moderato",
  SEV4: "Basso",
};

export const SEVERITY_CLASS: Record<Severity, string> = {
  SEV1: "bg-rose-50 text-rose-900 border-rose-200 dark:bg-rose-500/15 dark:text-rose-200 dark:border-rose-500/30",
  SEV2: "bg-orange-50 text-orange-900 border-orange-200 dark:bg-orange-500/15 dark:text-orange-200 dark:border-orange-500/30",
  SEV3: "bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-500/15 dark:text-amber-200 dark:border-amber-500/30",
  SEV4: "bg-slate-50 text-slate-800 border-slate-200 dark:bg-slate-500/15 dark:text-slate-200 dark:border-slate-500/30",
};

export const ALL_STATUSES: IncidentStatus[] = ["open", "active", "resolved"];

// Formatta i secondi MTTR in una stringa leggibile (es. "3h 15m").
export function formatMttr(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return "-";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${total}s`;
}

// Formatta un timestamp ISO/SQL in data+ora locale compatta.
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  // SQLite restituisce "YYYY-MM-DD HH:MM:SS" (UTC, senza timezone): lo trattiamo come UTC.
  const iso = value.includes("T") ? value : value.replace(" ", "T") + "Z";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
