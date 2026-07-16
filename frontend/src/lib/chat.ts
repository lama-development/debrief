// EventSource non supporta POST/Bearer: il flusso SSE viene letto con fetch.

import { API_URL, ApiError, getAuthToken } from "@/lib/api";
import type { ChatEvent } from "@/lib/types";

export async function streamChat(
  incidentId: string,
  message: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAuthToken();
  const res = await fetch(`${API_URL}/incidents/${incidentId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Errore ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      // Mantiene il messaggio generico.
    }
    throw new ApiError(res.status, detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flush = () => {
    let sep: number;
    // Nel protocollo SSE una riga vuota separa due blocchi consecutivi.
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      // Un blocco SSE può distribuire i dati su più righe.
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data) as ChatEvent);
      } catch {
        // Ignora un blocco malformato senza interrompere il flusso.
      }
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    flush();
  }
  // Gestisce un ultimo blocco privo del separatore finale.
  buffer += decoder.decode();
  if (buffer.length > 0) {
    buffer += "\n\n";
    flush();
  }
}
