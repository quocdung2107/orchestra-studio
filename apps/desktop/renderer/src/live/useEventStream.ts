import type { EventEnvelope } from "@orchestra/contracts";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { mergeEvents, queriesToRefresh } from "./eventLog";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

/**
 * Company-scoped SSE subscription. EventSource reconnects by itself and sends
 * Last-Event-ID, so the server resumes after the last sequence we saw.
 */
export function useEventStream(companyId: string | null) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<EventEnvelope[]>([]);
  const [status, setStatus] = useState<StreamStatus>("closed");

  useEffect(() => {
    setEvents([]);
    if (!companyId) {
      setStatus("closed");
      return;
    }
    setStatus("connecting");
    const es = new EventSource(`/api/v1/companies/${encodeURIComponent(companyId)}/events/stream`);
    es.onopen = () => setStatus("open");
    es.onerror = () => setStatus(es.readyState === EventSource.CLOSED ? "closed" : "reconnecting");
    es.addEventListener("event", (msg) => {
      let ev: EventEnvelope;
      try {
        ev = JSON.parse((msg as MessageEvent<string>).data) as EventEnvelope;
      } catch {
        return; // malformed frame: ignore rather than corrupt state
      }
      setEvents((cur) => mergeEvents(cur, [ev]));
      for (const key of queriesToRefresh(ev)) qc.invalidateQueries({ queryKey: key });
    });
    return () => {
      es.close();
      setStatus("closed");
    };
  }, [companyId, qc]);

  return { events, status };
}
