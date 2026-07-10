// streamChat: consuma la chat SSE del backend (POST autenticato).
//
// Perché non EventSource? L'API EventSource del browser supporta solo GET e non
// permette header custom (serve il Bearer). Quindi facciamo fetch() in POST e
// leggiamo manualmente il ReadableStream: bufferizziamo, splittiamo i frame su
// "\n\n" e parsiamo la parte dopo "data: " (stesso framing di service.sse_frame).

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
      // corpo non-JSON
    }
    throw new ApiError(res.status, detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Estrae e processa tutti i frame SSE completi presenti nel buffer.
  const flush = () => {
    let sep: number;
    // Un frame termina con una riga vuota: "\n\n".
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      // Un frame può avere più righe; concateniamo i payload "data:" (spec SSE).
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data) as ChatEvent);
      } catch {
        // frame non parsabile: lo ignoriamo invece di rompere lo stream.
      }
    }
  };

  // Loop di lettura: ogni chunk viene decodificato, accodato e processato.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    flush();
  }
  // Eventuale frame finale senza "\n\n" di chiusura.
  buffer += decoder.decode();
  if (buffer.length > 0) {
    buffer += "\n\n";
    flush();
  }
}
