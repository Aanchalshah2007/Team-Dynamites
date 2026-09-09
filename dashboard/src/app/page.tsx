"use client";

import { useEffect, useState } from "react";
import { collection, query, orderBy, limit, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";

type TelemetryEvent = {
  id: string;
  event?: string;
  ts?: string;
  stale_gen?: number;
  current_gen?: number;
  task_kind?: string;
  provider?: string;
  generation_id?: number;
  text?: string;
  [key: string]: unknown;
};

const badgeColor: Record<string, string> = {
  fenced_drop: "#f85149",
  active_speech_provider: "#58a6ff",
  turn: "#3fb950",
  stress_test_run: "#d29922",
};

export default function Dashboard() {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);

  useEffect(() => {
    const q = query(collection(db, "telemetry"), orderBy("ts", "desc"), limit(50));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setEvents(snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() } as TelemetryEvent)));
    });
    return unsubscribe;
  }, []);

  const fencedDropCount = events.filter((e) => e.event === "fenced_drop").length;
  const latestProvider = events.find((e) => e.event === "active_speech_provider")?.provider ?? "unknown";

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 600 }}>Mechatronics Lab Voice Assistant</h1>
      <p style={{ color: "#8b949e", marginTop: 4 }}>Live telemetry from backend/telemetry.py (Firestore)</p>

      <section style={{ display: "flex", gap: 16, margin: "24px 0" }}>
        <Stat label="Active speech provider" value={latestProvider} accent={latestProvider === "fallback" ? "#f85149" : "#3fb950"} />
        <Stat label="Fenced drops (last 50 events)" value={String(fencedDropCount)} accent="#58a6ff" />
        <Stat label="Events loaded" value={String(events.length)} accent="#8b949e" />
      </section>

      <h2 style={{ fontSize: 16, fontWeight: 600, marginTop: 32 }}>Event feed</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
        {events.length === 0 && (
          <p style={{ color: "#8b949e" }}>
            No events yet. Run <code>python evidence/stress_test.py --n 10</code> from the backend, or start
            a live session, to populate this feed.
          </p>
        )}
        {events.map((e) => (
          <div
            key={e.id}
            style={{
              display: "flex",
              gap: 12,
              alignItems: "baseline",
              padding: "10px 14px",
              border: "1px solid #21262d",
              borderRadius: 8,
              background: "#111820",
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: 999,
                background: badgeColor[e.event ?? ""] ?? "#30363d",
                color: "#0b0f14",
                whiteSpace: "nowrap",
              }}
            >
              {e.event ?? "event"}
            </span>
            <span style={{ fontSize: 13, color: "#c9d1d9", flex: 1 }}>{summarize(e)}</span>
            <span style={{ fontSize: 11, color: "#6e7681" }}>{e.ts}</span>
          </div>
        ))}
      </div>
    </main>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div style={{ flex: 1, border: "1px solid #21262d", borderRadius: 10, padding: "14px 16px", background: "#111820" }}>
      <div style={{ fontSize: 12, color: "#8b949e" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: accent, marginTop: 4 }}>{value}</div>
    </div>
  );
}

function summarize(e: TelemetryEvent): string {
  switch (e.event) {
    case "fenced_drop":
      return `stale gen ${e.stale_gen} dropped (current gen ${e.current_gen}, ${e.task_kind})`;
    case "active_speech_provider":
      return `now speaking via ${e.provider}`;
    case "turn":
      return e.text ? `gen ${e.generation_id}: "${e.text}"` : `gen ${e.generation_id}`;
    case "stress_test_run":
      return `run ${e.run_index}: stop=${(e as any).time_to_stop_audio_ms?.toFixed?.(1)}ms`;
    default:
      return JSON.stringify(e);
  }
}
